#!/usr/bin/env python3

from random import sample
from struct import unpack, unpack_from
from copy import copy
import numpy as np
#from crcmod.predefined import mkCrcFun

class Section:
    def __init__(self, buf):
        self.read(buf)

    def read(self, buf):
        header = unpack('<HHIBB6s', buf[:16])
        self.crc = header[0]
        # crc preset xmodem
        # quirk: bytes may be swapped
        self.id = header[1]
        self.size = header[2]
        self.section_version = header[3]
        self.protocol_version = header[4]
        self.reserved = header[5]
        self.data = buf[16:]
        self.raw_data = buf
        ## ignore crc
        #crc16 = mkCrcFun('xmodem')
        #self.crc_calc = crc16(buf[2:])
        #print(self.id, hex(self.crc), hex(self.crc_calc))

    def __str__(self):
        data = copy(self.__dict__)
        return self.__class__.__name__ + str(data)


class Segment:
    """ decodes SCP-ECG files from Healforce devices """
    def __init__(self, filename, read_metadata_only=False):
        with open(filename, 'rb') as f:
            crc, filesize = unpack('<HL', f.read(6))
            self.samples = []
            self.samples_beat = []
            self.samples_marked_beat = []
            
            self._read_section_0(f)
            for section_id in self.section_offsets:
                f.seek(self.section_offsets[section_id])
                buf = f.read(self.section_sizes[section_id])
                if section_id == 1:
                    self._read_section_1(buf)
                # section 2 contains a short huffman table, but the data is not huffman encoded
                # ignoring section 3 as it does not seem to be working with PC-80B
                #if section_id == 3:
                #    self._read_section_3(buf)
                #    if read_metadata_only:
                #        break
                if section_id == 6:
                    self._read_section_6(buf, num_leads=1)
                    # quirk: number of rhythm data streams is always 1,
                    #        >1 streams are interleaved
                if section_id == 9:
                    self._read_section_9(buf)
                else:
                    pass

    def _read_section_0(self, f):
        """ SCP ECG Header """
        buf = f.read(8)
        size = unpack('<HHI', buf)[2]
        buf += f.read(size - 8)
        s = Section(buf)
        offset = 0
        self.section_offsets = {}
        self.section_sizes = {}
        while offset < len(s.data):
            entry = unpack_from('<HII', s.data, offset)
            section_id = entry[0]
            self.section_sizes[section_id] = entry[1]
            self.section_offsets[section_id] = entry[2]
            offset += 10


    def _read_section_1(self, buf):
        """ Patient Data """
        s = Section(buf)
        offset = 0
        self.patient_info = {}
        while offset < len(s.data):
            entry = unpack('<BH', s.data[offset:offset+3])
            tag = entry[0]
            size = entry[1]
            if size == 0 or size > len(s.data):
                break
            data = s.data[offset+3:offset+3+size]
            if tag == 2:
                self.patient_info['id'] = data.decode(encoding="utf-8", errors="replace").strip('\x00')
            elif tag == 25:
                self.patient_info['startdate'] = unpack('>HBB', data)
            elif tag == 26:
                self.patient_info['starttime'] = unpack('>BBB', data)
            else:
                self.patient_info[str(tag)] = data
            offset += 3+size


    #def _read_section_3(self, buf):
    #    """ ECG lead definition """
    #    s = Section(buf)
    #    self.num_leads = s.data[0]
    #    print(self.num_leads)
    #    self.sample_number_start = unpack('>I', s.data[2:6])
    #    self.sample_number_end = unpack('>I', s.data[2:6])
    #    offset = 0


    def _read_section_6(self, buf, num_leads=1):
        """ Rhythm data """
        s = Section(buf)
        header = unpack('<HHHH', s.raw_data[15:15+8])
        self.amplitude_value_multiplier = header[0]
        print(f"Amplitude: {self.amplitude_value_multiplier}")
        self.sample_time_interval = header[1]
        print(f"Interval: {self.sample_time_interval}")
        # Not sure what index 2 does...
        self.data_len = header[3]
        print(f"Data length: {self.data_len}")

        self.number_of_samples = int(self.data_len / 2)
        # PC-180D stuff
        #self.bimodal_compression_used = header[3]
        #print(self.bimodal_compression_used)
        #compressed_offset = 8+(num_leads*2)
        ptr = 15+8
        while ptr < len(s.data):
            val = unpack_from('<H', s.raw_data, ptr)[0]
            ptr += 2  # Move the pointer by the size of the 16-bit integer
            
            # This is not working
            self.samples_beat.append(val & 0x8000 >> 15)
            self.samples_marked_beat.append(val & 0x4000 >> 14)

            # Mask out the upper 4 bits (0xFFF keeps the lower 12 bits)
            val &= 0xFFF
            
            # Convert the 12-bit value to a signed value centered around 0
            sample = float(val) - 2048.0
            
            # Convert to nanovolts and then to millivolts using the amplitude
            sample *= float(self.amplitude_value_multiplier)  # Convert to nanovolts
            sample /= 1000000.0         # Convert to millivolts (from nanovolts)
            
            # Store the sample
            self.samples.append(sample)
        # for the 4th sample, take 4 bits from each of previous 3 words
        #samples[:,3] = ((samples[:,0] & 0x3C00) >> 2) + ((samples[:,1] & 0x3C00) >> 6) + ((samples[:,2] & 0x3C00) >> 10)
        # heart beat (QRS) detected by hardware
        #self.beats = (samples & 0x8000) >> 15
        # irregular heart beat detected by hardware - details are in section 9
        #self.marked_beats = (samples & 0x4000) >> 14
        # this converts the 10-bit data into regular 16-bit signed integers
        #  the high byte of the 10-bit data indicate sign or rather range of the sample
        #samples = (((((samples & 0x0300) >> 8) + 0xFE) & 0xFF) << 8) + (samples & 0xFF)
        # samples are quantized in 0.01 mV steps, i.e. 100 ~= 1 mV
        #self.compressed_samples = []
        #offset = 8
        #for _ in range(self.number_of_samples):
        #    data = s.data[offset:offset+2]
        #    #assert(len(data) == size), f"Size mismatch {len(data)} {size}"
        #    self.compressed_samples.append(data)
        #    offset += 2


    def _read_section_9(self, buf):
        """ Event data """
        self.low_freq_heart_rate = list(unpack('<HHHHHH', buf[0x44:0x44+12]))
        self.heart_rate = []
        self.other = [] # not yet known
        self.flags = []
        self.irregular_beat_markers = []

        t = unpack('<IHHBBH', buf[0x10:0x1c])
        if t[0] != 0x20000 or t[1] != 0x200:
            print("unusual section 9 (header)")
            print(hex(t[0]), hex(t[1]), t[5])

        page = t[2]
        self.irregular_beat_detected = (t[5] == 0)
        #heart_beats_list_size = t[4]

        offset = 0
        last_heart_rate = 0
        while 0x134+offset+4 < len(buf):
            t = unpack('<BBBB', buf[0x134+offset:0x134+offset+4])

            # averaged heart rate
            #  if you want the beat-to-beat heart rate,
            #  use data in section 6
            last_heart_rate = t[0]
            if last_heart_rate == 0xff:
                break
            self.heart_rate.append(last_heart_rate)

            # not known what this indicates
            self.other.append(t[1])

            # irregular beat markers
            m = t[3]
            # remapping same event types
            if m == 0x0e:
                m = 8
            elif m == 0x0f:
                m = 9
            elif m == 0x13:
                m = 10
            elif m == 0x14:
                m = 11
            self.irregular_beat_markers.append(m)

            # heart beat flags
            f = t[2]
            self.flags.append(f)
            # no idea what most flags mean
            # 0x20 and 0x80 seem to indicate motion

            offset += 4
