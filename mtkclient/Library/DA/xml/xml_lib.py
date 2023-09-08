#!/usr/bin/python3
# -*- coding: utf-8 -*-
# (c) B.Kerler 2018-2023 GPLv3 License
import logging
import time
import os
from binascii import hexlify
from struct import pack, unpack

from mtkclient.Library.DA.xml.xml_param import DataType, FtSystemOSE, LogLevel
from mtkclient.Library.utils import LogBase, logsetup
from mtkclient.Library.error import ErrorHandler
from mtkclient.Library.DA.daconfig import EMMC_PartitionType, UFS_PartitionType, DaStorage
from mtkclient.Library.partition import Partition
from mtkclient.config.payloads import pathconfig
from mtkclient.Library.settings import hwparam
from mtkclient.Library.thread_handling import writedata, Queue, Thread
from mtkclient.Library.DA.xml.xml_cmd import *

rq = Queue()


class upfile:
    def __init__(self, checksum, info, target_file, packet_length):
        self.checksum = checksum
        self.info = info
        self.target_file = target_file
        self.packet_length = packet_length


class dwnfile:
    def __init__(self, checksum, info, source_file, packet_length):
        self.checksum = checksum
        self.info = info
        self.source_file = source_file
        self.packet_length = packet_length

class DAXML(metaclass=LogBase):
    def __init__(self, mtk, daconfig, loglevel=logging.INFO):
        self.__logger = logsetup(self, self.__logger, loglevel, mtk.config.gui)
        self.Cmd = XMLCmd(mtk)
        self.mtk = mtk
        self.loglevel = loglevel
        self.daext = False
        self.sram = None
        self.dram = None
        self.emmc = None
        self.nand = None
        self.nor = None
        self.ufs = None
        self.chipid = None
        self.randomid = None
        self.__logger = self.__logger
        self.eh = ErrorHandler()
        self.config = self.mtk.config
        self.usbwrite = self.mtk.port.usbwrite
        self.usbread = self.mtk.port.usbread
        self.echo = self.mtk.port.echo
        self.rbyte = self.mtk.port.rbyte
        self.rdword = self.mtk.port.rdword
        self.rword = self.mtk.port.rword
        self.daconfig = daconfig
        self.partition = Partition(self.mtk, self.readflash, self.read_pmt, loglevel)
        self.pathconfig = pathconfig()
        self.patch = False
        self.generatekeys = self.mtk.config.generatekeys
        if self.generatekeys:
            self.patch = True

    def xsend(self, data, datatype=DataType.DT_PROTOCOL_FLOW, is64bit: bool = False):
        if isinstance(data, int):
            if is64bit:
                data = pack("<Q", data)
                length = 8
            else:
                data = pack("<I", data)
                length = 4
        else:
            if type(data) == str:
                length = len(data) + 1
            else:
                length = len(data)
        tmp = pack("<III", self.Cmd.MAGIC, datatype, length)
        if self.usbwrite(tmp):
            if type(data)==str:
                return self.usbwrite(bytes(data, 'utf-8') + b"\x00")
            else:
                return self.usbwrite(data)
        return False

    def ack(self):
        return self.xsend("OK")

    def ack_value(self, length):
        return self.xsend(f"OK@{hex(length)}")

    def setup_env(self):
        da_log_level = int(self.daconfig.uartloglevel)
        loglevel = "INFO"
        if da_log_level == 0:
            loglevel = LogLevel().TRACE
        elif da_log_level == 1:
            loglevel = LogLevel().DEBUG
        elif da_log_level == 2:
            loglevel = LogLevel().INFO
        elif da_log_level == 3:
            loglevel = LogLevel().WARN
        elif da_log_level == 4:
            loglevel = LogLevel().ERROR
        system_os = FtSystemOSE.OS_LINUX
        res = self.send_command(self.Cmd.cmd_set_runtime_parameter(da_log_level=loglevel, system_os=system_os))
        return res

    def send_command(self, xmldata, noack:bool=False):
        if self.xsend(xmldata):
            result = self.get_response()
            if result == "OK":
                if noack:
                    return True
                cmd, result = self.get_command_result()
                if cmd == "CMD:END" and result == "OK":
                    self.ack()
                    scmd, sresult = self.get_command_result()
                    if scmd == "CMD:START":
                        return True
                else:
                    return result
            elif result == "ERR!UNSUPPORTED":
                scmd, sresult = self.get_command_result()
                self.ack()
                tcmd, tresult = self.get_command_result()
                if tcmd == "CMD:START":
                    return sresult
            elif "ERR!" in result:
                return result
        return False

    def get_field(self, data, fieldname):
        start = data.find(f"<{fieldname}>")
        if start!=-1:
            end = data.find(f"</{fieldname}>",start+len(fieldname)+2)
            if start!=-1 and end!=-1:
                return data[start+len(fieldname)+2:end]
        return ""

    def get_response(self) -> str:
        sync = self.usbread(4 * 3)
        if len(sync) == 4 * 3:
            if int.to_bytes(sync[:4], 'little') == 0xfeeeeeef:
                if int.to_bytes(sync[4:8], 'little') == 0x1:
                    length = int.to_bytes(sync[8:12])
                    data = self.usbread(length)
                    if len(data) == length:
                        return bytes.decode(data.rstrip(b"\x00"), 'utf-8')
        return ""

    def get_response_data(self) -> bytes:
        sync = self.usbread(4 * 3)
        if len(sync) == 4 * 3:
            if int.to_bytes(sync[:4], 'little') == 0xfeeeeeef:
                if int.to_bytes(sync[4:8], 'little') == 0x1:
                    length = int.to_bytes(sync[8:12])
                    data = self.usbread(length)
                    if len(data) == length:
                        return data
        return b""

    def upload_da1(self):
        if self.daconfig.da_loader is None:
            self.error("No valid da loader found... aborting.")
            return False
        loader = self.daconfig.loader
        self.info(f"Uploading xflash stage 1 from {os.path.basename(loader)}")
        if not os.path.exists(loader):
            self.info(f"Couldn't find {loader}, aborting.")
            return False
        with open(loader, 'rb') as bootldr:
            # stage 1
            da1offset = self.daconfig.da_loader.region[1].m_buf
            da1size = self.daconfig.da_loader.region[1].m_len
            da1address = self.daconfig.da_loader.region[1].m_start_addr
            da2address = self.daconfig.da_loader.region[1].m_start_addr
            da1sig_len = self.daconfig.da_loader.region[1].m_sig_len
            bootldr.seek(da1offset)
            da1 = bootldr.read(da1size)
            # ------------------------------------------------
            da2offset = self.daconfig.da_loader.region[2].m_buf
            da2sig_len = self.daconfig.da_loader.region[2].m_sig_len
            bootldr.seek(da2offset)
            da2 = bootldr.read(self.daconfig.da_loader.region[2].m_len)

            da1offset = self.daconfig.da_loader.region[1].m_buf
            da1size = self.daconfig.da_loader.region[1].m_len
            da1address = self.daconfig.da_loader.region[1].m_start_addr
            da2address = self.daconfig.da_loader.region[1].m_start_addr
            da1sig_len = self.daconfig.da_loader.region[1].m_sig_len
            bootldr.seek(da1offset)
            da1 = bootldr.read(da1size)
            # ------------------------------------------------
            da2offset = self.daconfig.da_loader.region[2].m_buf
            da2sig_len = self.daconfig.da_loader.region[2].m_sig_len
            bootldr.seek(da2offset)
            da2 = bootldr.read(self.daconfig.da_loader.region[2].m_len)
            self.daconfig.da2 = da2[:-da2sig_len]

            if self.mtk.preloader.send_da(da1address, da1size, da1sig_len, da1):
                self.info("Successfully uploaded stage 1, jumping ..")
                if self.mtk.preloader.jump_da(da1address):
                    cmd, result = self.get_command_result()
                    if cmd == "CMD:START":
                        self.setup_env()
                        self.setup_hw_init()
                        self.setup_host_info()
                        return True
                    else:
                        return False
                else:
                    self.error("Error on jumping to DA.")
            else:
                self.error("Error on sending DA.")
        return False

    def setup_hw_init(self):
        res = self.send_command(self.Cmd.cmd_host_supported_commands(host_capability="CMD:DOWNLOAD-FILE^1@CMD:FILE-SYS-OPERATION^1@CMD:PROGRESS-REPORT^1@CMD:UPLOAD-FILE^1@"))
        res = self.send_command(self.Cmd.cmd_notify_init_hw())
        return True

    def setup_host_info(self,hostinfo:str=""):
        res = self.send_command(self.Cmd.cmd_set_host_info(hostinfo))
        return res

    def get_command_result(self):
        data = self.get_response()
        cmd = self.get_field(data,"command")
        result = ""
        if cmd == "CMD:START":
            self.ack()
            return cmd, "START"
        if cmd=="CMD:DOWNLOAD-FILE":
            """
            <?xml version="1.0" encoding="utf-8"?><host><version>1.0</version>
            <command>CMD:DOWNLOAD-FILE</command>
            <arg>
                <checksum>CHK_NO</checksum>
                <info>2nd-DA</info>
                <source_file>MEM://0x7fe83c09a04c:0x50c78</source_file>
                <packet_length>0x1000</packet_length>
            </arg></host>
            """
            checksum = self.get_field(data,"checksum")
            info = self.get_field(data,"info")
            source_file = self.get_field(data, "source_file")
            packet_length = self.get_field(data, "packet_length")
            self.ack()
            return cmd, dwnfile(checksum,info,source_file,packet_length)
        elif cmd=="CMD:PROGRESS-REPORT":
            """
            <?xml version="1.0" encoding="utf-8"?><host><version>1.0</version>
            <command>CMD:PROGRESS-REPORT</command>
            <arg>
                <message>init-hw</message>
            </arg></host>
            """
            self.ack()
            data = ""
            while data != "OK!EOT":
                data = self.get_response()
                self.ack()
            data = self.get_response()
            cmd = self.get_field(data, "command")
        elif cmd=="CMD:UPLOAD-FILE":
            checksum = self.get_field(data, "checksum")
            info = self.get_field(data, "info")
            target_file = self.get_field(data, "target_file")
            packet_length = self.get_field(data, "packet_length")
            self.ack()
            return cmd, upfile(checksum,info,target_file,packet_length)
        if cmd=="CMD:END":
            result = self.get_field(data,"result")
            if "message" in data and result !="OK":
                message = self.get_field(data,"message")
                return cmd, message
        return cmd, result

    def upload(self, result, data):
        if type(result)==dwnfile:
            checksum, info, source_file, packet_length = result
            tmp = source_file.split(":")[2]
            length = int(tmp[2:], 16)
            self.ack_value(length)
            resp = self.get_response()
            if resp == "OK":
                for pos in range(0, length, packet_length):
                    self.ack_value(0)
                    self.xsend(data=data[pos:pos + packet_length])
                    resp = self.get_response()
                    if resp != "OK":
                        self.error(f"Error on writing stage2 at pos {hex(pos)}")
                        return False
                    cmd, result = self.get_command_result()
                    self.ack()
                    if cmd == "CMD:END" and result=="OK":
                        cmd, result = self.get_command_result()
                        if cmd=="CMD:START":
                            self.ack()
                            return True
                return True
            return False
        else:
            self.error("No upload data received. Aborting.")
            return False

    def download(self, result):
        if type(result)==upfile:
            checksum, info, target_file, packet_length = result
            resp = self.get_response()
            if "OK@" in resp:
                tmp = resp.split("@")[1]
                length = int(tmp[2:], 16)
                self.ack()
                sresp = self.get_response()
                if sresp == "OK":
                    self.ack()
                    data=bytearray()
                    while length>0:
                        tmp = self.get_response_data()
                        length-=len(tmp)
                        data.extend(tmp)
                        self.ack()
                    return data
            self.error("Error on downloading data:"+resp)
            return False
        else:
            self.error("No download data received. Aborting.")
            return False

    def boot_to(self, da2, da2offset):
        result = self.send_command(self.Cmd.cmd_boot_to(at_addr=da2offset, jmp_addr=da2offset, length=len(da2)))
        if type(result) == dict:
            self.info("Uploading stage 2...")
            if self.upload(result,da2):
                self.info("Successfully uploaded stage 2.")
        else:
            self.error("Wrong boot_to response :(")
        return False


    def upload_da(self):
        if self.upload_da1():
            self.info("Stage 1 successfully loaded.")
            da2 = self.daconfig.da2
            da2offset = self.daconfig.da_loader.region[2].m_buf
            if self.boot_to(da2,da2offset):
                self.info("Successfully uploaded stage 2")
                self.setup_hw_init()
                self.change_usb_speed()
                res=self.check_sla()
                if type(res)==bool:
                    if not res:
                        self.info("SLA is disabled")
                    else:
                        self.info("SLA is enabled")
                else:
                    self.error(res)
                self.daext = False
                self.storage = self.get_hw_info()
                self.reinit(True)
                self.check_lifecycle()
                parttbl = self.read_partition_table()
                self.config.hwparam.writesetting("hwcode", hex(self.config.hwcode))
                return True
        return False

    def get_hw_info(self):
        self.send_command(self.Cmd.cmd_get_hw_info(),noack=True)
        cmd, result = self.get_command_result()
        data = self.download(result)
        """
        <?xml version="1.0" encoding="utf-8"?>
        <da_hw_info>
        <version>1.2</version>
        <ram_size>0x100000000</ram_size>
        <battery_voltage>3810</battery_voltage>
        <random_id>4340bfebf6ace4e325f71f7d37ab15aa</random_id>
        <storage>UFS</storage>
        <ufs>
            <block_size>0x1000</block_size>
            <lua0_size>0x400000</lua0_size>
            <lua1_size>0x400000</lua1_size>
            <lua2_size>0xee5800000</lua2_size>
            <lua3_size>0</lua3_size>
            <id>4D54303634474153414F32553231202000000000</id>
        </ufs>
        <product_id></product_id>
        </da_hw_info>
        """
        scmd, sresult = self.get_command_result()
        self.ack()
        if sresult == "OK":
            tcmd, tresult = self.get_command_result()
            if tresult=="START":
                storage = self.get_field(data, "storage")
                class storage_info:
                    def __init__(self, storagetype, data):
                        self.storagetype = storagetype
                        if self.storagetype == "UFS":
                            self.block_size = self.get_field(data,"block_size")
                            self.lua0_size = self.get_field(data,"lua0_size")
                            self.lua1_size = self.get_field(data,"lua1_size")
                            self.lua2_size = self.get_field(data,"lua2_size")
                            self.lua3_size = self.get_field(data,"lua3_size")
                            self.cid = self.get_field(data,"id")
                        elif self.storagetype == "EMMC":
                            self.block_size = self.get_field(data, "block_size")
                            self.boot1_size = self.get_field(data, "boot1_size")
                            self.boot2_size = self.get_field(data, "boot2_size")
                            self.rpmb_size = self.get_field(data, "rpmb_size")
                            self.user_size = self.get_field(data, "user_size")
                            self.gp1_size = self.get_field(data, "gp1_size")
                            self.gp2_size = self.get_field(data, "gp2_size")
                            self.gp3_size = self.get_field(data, "gp3_size")
                            self.gp4_size = self.get_field(data, "gp4_size")
                            self.cid = self.get_field(data, "id")
                        elif self.storagetype == "NAND":
                            self.block_size = self.get_field(data, "block_size")
                            self.page_size = self.get_field(data, "page_size")
                            self.spare_size = self.get_field(data, "spare_size")
                            self.total_size = self.get_field(data, "total_size")
                            self.cid = self.get_field(data, "id")
                            self.page_parity_size = self.get_field(data, "page_parity_size")
                            self.sub_type = self.get_field(data, "sub_type")
                        else:
                            self.error(f"Unknown storage type: {storage}")
                return storage_info(storagetype=storage,data=data)

    def check_sla(self):
        data=self.get_sys_property(key="DA.SLA", length=0x200000)
        data = data.decode('utf-8')
        if "item key=" in data:
            tmp=data[data.find("item key=")+8]
            res=tmp[tmp.find(">")+1:tmp.find("<")]
            if res=="DISABLED":
                return False
            else:
                return True
        else:
            self.error("Couldn't find item key")
        return data


    def get_sys_property(self, key:int="DA.SLA", length:int=0x200000):
        self.send_command(self.Cmd.cmd_get_sys_property(key=key,length=length),noack=True)
        cmd, result = self.get_command_result()
        data = self.download(result)
        # CMD:END
        scmd, sresult = self.get_command_result()
        self.ack()
        if sresult == "OK":
            tcmd, tresult = self.get_command_result()
            if tresult=="START":
                return data
        return None

    def change_usb_speed(self):
        resp = self.send_command(self.Cmd.cmd_can_higher_usb_speed())
        if "Unsupported" in resp:
            return False

    def read_partition_table(self):
        self.send_command(self.Cmd.cmd_read_partition_table(),noack=True)
        cmd, result = self.get_command_result()
        if "Unsupported" in result:
            return False
        data = self.download(result)
        # CMD:END
        scmd, sresult = self.get_command_result()
        self.ack()
        self.ack()
        if sresult == "OK":
            tcmd, tresult = self.get_command_result()
            class partitiontable:
                def __init__(self,name,start,size):
                    self.name=name
                    self.start=int(start,16)
                    self.size=int(size,16)
            if tresult=="START":
                parttbl=[]
                for item in data.split("<pt>"):
                    name=self.get_field(item,"name")
                    start = self.get_field(item, "start")
                    size = self.get_field(item, "size")
                    parttbl.append(partitiontable(name,start,size))
                return parttbl
        return None
    def check_lifecycle(self):
        self.send_command(self.Cmd.cmd_emmc_control(function="LIFE-CYCLE-STATUS"),noack=True)
        cmd, result = self.get_command_result()
        if "Unsupported" in result:
            return False
        data = self.download(result)
        scmd, sresult = self.get_command_result()
        self.ack()
        if sresult == "OK":
            tcmd, tresult = self.get_command_result()
            if tresult == "START":
                if data==b"OK":
                    return True
                else:
                    return False
        return False

    def reinit(self, display=False):
        self.config.hwparam = hwparam(self.config.meid, self.config.hwparam_path)
        """
        self.config.sram, self.config.dram = self.get_ram_info()
        self.emmc = self.get_emmc_info(display)
        self.nand = self.get_nand_info(display)
        self.nor = self.get_nor_info(display)
        self.ufs = self.get_ufs_info(display)
        """
        if self.storage.storagetype == "EMMC":
            self.daconfig.flashtype = "emmc"
            self.daconfig.flashsize = self.storage.user_size
            self.daconfig.rpmbsize = self.storage.rpmb_size
            self.daconfig.boot1size = self.storage.boot1_size
            self.daconfig.boot2size = self.storage.boot2_size
        elif self.storage.storagetype == "NAND":
            self.daconfig.flashtype = "nand"
            self.daconfig.flashsize = self.storage.total_size
            self.daconfig.rpmbsize = 0
            self.daconfig.boot1size = 0x400000
            self.daconfig.boot2size = 0x400000
        elif self.storage.storagetype == "UFS":
            self.daconfig.flashtype = "ufs"
            self.daconfig.flashsize = self.storage.lua0_size
            self.daconfig.rpmbsize = self.storage.lua1_size
            self.daconfig.boot1size = self.storage.lua1_size
            self.daconfig.boot2size = self.storage.lua2_size
        """
        self.chipid = self.get_chip_id()
        self.daversion = self.get_da_version()
        self.randomid = self.get_random_id()
        speed = self.get_usb_speed()
        if speed == b"full-speed" and self.daconfig.reconnect:
            self.info("Reconnecting to stage2 with higher speed")
            self.config.set_gui_status(self.config.tr("Reconnecting to stage2 with higher speed"))
            self.set_usb_speed()
            self.mtk.port.close(reset=True)
            time.sleep(2)
            while not self.mtk.port.cdc.connect():
                time.sleep(0.5)
            self.info("Connected to stage2 with higher speed")
            self.mtk.port.cdc.set_fast_mode(True)
            self.config.set_gui_status(self.config.tr("Connected to stage2 with higher speed"))
        """
