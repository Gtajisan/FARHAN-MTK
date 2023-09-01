max_node_value_length = 256
max_address_length = 9
max_xml_data_length = 0x200000

def create_cmd(cmd: str, arg:str="", adv:str=""):
    args=f"""<arg>{arg}</arg>"""
    cmd = f"""<?xml version="1.0" encoding="utf-8"?>
    <da>
        <version>1.0</version>
        <command>CMD:{cmd}</command>
        {args}
        {adv}
    </da>"""
    return cmd

################ DA1 ######################

def cmd_notify_init_hw():
    cmd = create_cmd("NOTIFY-INIT-HW")
    return cmd

"""
def cmd_set_host_info(hostinfo:str="2002.02.03T11.22.33-PC11123445"):
"""

def cmd_boot_to(at_addr:int=0x2000000, jmp_addr:int=0x2000000, mem_offset:int=0x8000000, mem_length:int=0x100000):
    arg = f"""<at_address>{hex(at_addr)}</at_address>
        <jmp_address>{hex(jmp_addr)}</jmp_address>
        <source_file>MEM://{hex(mem_offset)}:{hex(mem_length)}</source_file>"""
    cmd = create_cmd("BOOT-TO", arg)
    return cmd

"""
def cmd_reboot(disconnect: bool = False):
def cmd_get_hw_info(mem_offset=0x8000000, mem_length=0x100000):
"""

def cmd_set_runtime_parameter(checksum_level:str="USB",battery_exist:str="AUTO-DETECT",da_log_level:str="INFO",log_channel:str="UART",system_os:str="LINUX",version:str=None,initialize_dram:str=None):
    arg = f"""<checksum_level>{checksum_level}</checksum_level>
        <da_log_level>{da_log_level}</da_log_level>
        <log_channel>{log_channel}</da_log_channel>
        <battery_exist>{battery_exist}</battery_exist>
        <system_os>{system_os}</system_os>"""
    if version is not None:
        arg += f"""<version>{version}</version>"""
    # checksum_level (NONE,USB,STORAGE,USB-STORAGE)
    # da_log_level (TRACE,DEBUG,INFO,WARN,ERROR)
    # log_channel (USB/UART)
    # battery_exist (YES,NO,AUTO-DETECT)
    adv=""
    if initialize_dram is not None:
        adv = f"""<adv><initialize_dram>NO</initialize_dram></adv>"""
    cmd = create_cmd("SET-RUNTIME-PARAMETER",arg,adv)
    return cmd

def cmd_host_supported_commands(host_capability:str=""):
    arg = f"""<host_capability>{host_capability}</host_capability>"""
    cmd = create_cmd("HOST-SUPPORTED-COMMANDS",arg)
    return cmd

def cmd_ram_test(function:str="FLIP",start_address:int=0x4000000,length:int=0x100000,repeat:int=0xA):
    if function=="FLIP":
        arg = f"""<function>FLIP</function>
            <start_address>{hex(start_address)}</start_address>
            <length>{hex(length)}</length>
            <repeat>{hex(repeat)}</repeat>"""
    else:
        arg=f"""<function>CALIBRATION</function>
           <target_file>ms-appdata:///local/calib.bin</target_file>"""
    cmd = create_cmd("RAM-TEST",arg)
    resp="""
    <?xml version=\"1.0\" encoding=\"utf-8\"?><host><version>1.0</version><command>CMD:UPLOAD-FILE</command><arg><checksum>CHK_NO</checksum><info>WriteLocalFile</info><target_file>%s</target_file><packet_length>0x%x</packet_length></arg></host>
    <?xml version=\"1.0\" encoding=\"utf-8\"?><host><version>1.0</version><command>CMD:PROGRESS-REPORT</command><arg><message>RAM test.</message></arg></host>
    or
    <?xml version=\"1.0\" encoding=\"utf-8\"?><host><version>1.0</version><command>CMD:PROGRESS-REPORT</command><arg><message>Interface diag</message></arg></host>
    """
    return cmd

def cmd_dram_repair(mem_offset:int=0x10000,mem_length:int=0x1000):
    arg = f"""<param_file>D:/dram.info</param_file>
        <target_file>MEM://{mem_offset}:{mem_length}</target_file>"""
    cmd = create_cmd("DRAM-REPAIR",arg)
    # INFO Result: SUCCEEDED, NO-NEED, FAILED
    return cmd

################ DA2 ######################

def cmd_write_efuse():
    arg = f"""<source_file>ms-appdata:///local/efuse.xml</source_file>"""
    cmd = create_cmd("WRITE-EFUSE", arg)
    resp = """
    <?xml version=\"1.0\" encoding=\"utf-8\"?><host><version>1.0</version><command>CMD:DOWNLOAD-FILE</command><a"rg><checksum>%s</checksum><info>%s</info><source_file>%s</source_file><packet_length>0x%x</packet_length></arg></host>
    """
    return cmd


def cmd_read_efuse():
    arg = f"""<target_file>ms-appdata:///local/efuse.xml</target_file>"""
    cmd = create_cmd("READ-EFUSE", arg)
    resp = """
    <?xml version=\"1.0\" encoding=\"utf-8\"?><host><version>1.0</version><command>CMD:UPLOAD-FILE</command><arg><"checksum>CHK_NO</checksum><info>%s</info><target_file>%s</target_file><packet_length>0x%x</packet_length></arg></host>
    OK@0x%x (length)
    """
    return cmd


def cmd_get_hw_info(mem_offset=0x8000000, mem_length=0x100000):
    arg = f"""<target_file>MEM://{hex(mem_offset)}:{hex(mem_length)}</target_file>"""
    cmd = create_cmd("GET-HW-INFO", arg)
    resp = """ #EMMC
    <?xml version=\"1.0\" encoding=\"utf-8\"?><da_hw_info><version>1.2</version><ram_size>0x%llx</ram_size><battery_voltage>%d</battery_voltage><random_id>%s</random_id><storage>%s</storage><emmc><block_size>0x%x</block_size><boot1_size>0x%llx</boot1_size><boot2_size>0x%llx</boot2_size><rpmb_size>0x%llx</rpmb_size><user_size>0x%llx</user_size><gp1_size>0</gp1_size><gp2_size>0</gp2_size><gp3_size>0</gp3_size><gp4_size>0</gp4_size><id>%s</id></emmc><product_id>%s</product_id></da_hw_info>
    or #UFS
    <?xml version=\"1.0\" encoding=\"utf-8\"?><da_hw_info><version>1.2</version><ram_size>0x%llx</ram_size><battery_voltage>%d</battery_voltage><random_id>%s</random_id><storage>%s</storage><ufs><block_size>0x%x</block_size><lua0_size>0x%llx</lua0_size><lua1_size>0x%llx</lua1_size><lua2_size>0x%llx</lua2_size><lua3_size>0</lua3_size"><id>%s</id><ufs_vendor_id>0x%x</ufs_vendor_id><ufs_cid>%s</ufs_cid><ufs_fwver>%s</ufs_fwver></ufs><product_id>%s</product_id></da_hw_info>
    or #NAND
    <?xml version=\"1.0\" encoding=\"utf-8\"?><da_hw_info><version>1.2</version><ram_size>0x%llx</ram_size><battery_voltage>%d</battery_voltage><random_id>%s</random_id><storage>%s</storage><nand><block_size>0x%x</block_size><page_size>0x%x</page_size><spare_size>0x%x</spare_size><total_size>0x%llx</total_size><id>%s</id><page_parity_size>0x%x</page_parity_size><sub_type>%s</sub_type></nand><product_id>%s</product_id></da_hw_info>
    or #NONE
    <?xml version=\"1.0\" encoding=\"utf-8\"?><da_hw_info><version>1.0</version><ram_size>0x%llx</ram_size><battery_voltage>%d</battery_voltage><random_id>%s</random_id><storage>%s</storage></da_hw_info>
    """
    return cmd


def cmd_read_reg(bit_width: int = 32, base_address: int = 0x1000,mem_offset: int = 0x8000000, mem_length: int = 0x4):
    arg = f"""<bit_width>{bit_width}</bit_width>
        <base_address>{hex(base_address)}</base_address>
        <target_file>MEM://{hex(mem_offset)}:{hex(mem_length)}</target_file>"""
    cmd = create_cmd("READ-REGISTER", arg)
    resp = """
    <?xml version=\"1.0\" encoding=\"utf-8\"?><host><version>1.0</version><command>CMD:UPLOAD-FILE</command><arg><"checksum>CHK_NO</checksum><info>%s</info><target_file>%s</target_file><packet_length>0x%x</packet_length></arg></host>
    OK@0x%x (length)
    """
    return cmd


def cmd_write_reg(bit_width: int = 32, base_address: int = 0x1000, mem_offset: int = 0x8000000, mem_length: int = 0x4):
    arg = f"""<bit_width>{bit_width}</bit_width>
        <base_address>{hex(base_address)}</base_address>
        <source_file>MEM://{hex(mem_offset)}:{hex(mem_length)}</source_file>"""
    cmd = create_cmd("WRITE-REGISTER", arg)
    return cmd


def cmd_read_partition_name():
    cmd = ""
    return cmd


def cmd_debug_ufs():
    cmd = ""
    return cmd


def cmd_emmc_control(function: str = "GET-RPMB-STATUS", mem_offset=0x8000000, mem_length=0x100000):
    arg = f"""<function>{function}</function>
       <target_file>MEM://{hex(mem_offset)}:{hex(mem_length)}</target_file>"""
    cmd = create_cmd("EMMC-CONTROL", arg)
    return cmd


def cmd_reboot(disconnect: bool = False):
    if disconnect:
        action = "DISCONNECT"
    else:
        action = "IMMEDIATE"
    arg = f"""<action>{action}</action>"""
    cmd = create_cmd("REBOOT", arg)
    return cmd


def cmd_write_partition(partition:str="system", mem_offset:int=0x8000000, mem_length:int=0x100000):
    arg = f"""<partition>{partition}</partition>
        <source_file>MEM://{hex(mem_offset)}:{hex(mem_length)}"""
    cmd = create_cmd("WRITE-FLASH", arg)
    return cmd


def cmd_write_flash(partition: str = "EMMC-USER", offset: int = 0, mem_offset:int=0x8000000, mem_length:int=0x100000):
    arg = f"""<partition>{partition}</partition>
        <offset>{hex(offset)}</offset>
        <source_file>MEM://{hex(mem_offset)}:{hex(mem_length)}"""
    cmd = create_cmd("WRITE-FLASH", arg)
    return cmd


def cmd_read_partition(partition: str = "system"):
    arg = f"""<partition>{partition}</partition>
        <target_file>"C:/file.bin"</target_file>"""
    cmd = create_cmd("READ-PARTITION", arg)
    return cmd


def cmd_read_flash(partition: str = "EMMC-USER", offset: int = 0, length: int = 0x100000):
    arg = f"""<partition>{partition}</partition>
        <offset>{hex(offset)}</offset>
        <length>{hex(length)}</length>"""
    cmd = create_cmd("READ-FLASH", arg)
    return cmd


def cmd_flash_all():
    arg = f"""<path_separator>/</path_separator>
        <source_file>D:/scatter.xml</source_file>"""
    cmd = create_cmd("FLASH-ALL", arg)
    return cmd


def cmd_erase_partition(partition: str = "system"):
    arg = f"""<partition>{partition}</partition>"""
    cmd = create_cmd("ERASE-PARTITION", arg)
    return cmd


def cmd_erase_flash(partition: str = "EMMC-USER", offset: int = 0, length: int = 0x100000):
    arg = f"""<partition>{partition}</partition>
        <offset>{hex(offset)}</offset>
        <length>{hex(length)}</length>"""
    cmd = create_cmd("ERASE-FLASH", arg)
    return cmd


def cmd_flash_update():
    arg = f"""<path_separator>/</path_separator>
    <source_file>D:/scatter.xml</source_file>
    <backup_folder>D:/backup</backup_folder>"""
    cmd = create_cmd("FLASH-UPDATE", arg)
    return cmd


def cmd_write_partitions(partitions):
    flashlist=""
    for partition in partitions:
        flashlist+=f"<pt name={partition}>{partition}.img</pt>\n"
    arg = f"""<source_file>D:/scatter.xml</source_file>
    <flash_list>{flashlist}</flash_list>"""
    cmd = create_cmd("WRITE-PARTITIONS", arg)
    return cmd


def cmd_set_boot_mode(boot_mode):
    if boot_mode=="META":
        arg=f"""<mode>META</mode>
        <connect_type>WIFI</connect_type>
        <mobile_log>ON</mobile_log>
        <adb>ON</adb>"""
        # ADB = (ON,UART,USB)
    elif boot_mode=="FASTBOOT":
        arg=f"""<mode>META</mode>"""
    elif boot_mode=="ANDROID-TEST-MODE":
        arg = f"""<mode>ANDROID-TEST-MODE</mode>"""
    cmd = create_cmd("SET-BOOT-MODE", arg)
    return cmd


def cmd_set_rsc(key:str="k6885v1_64[op01]"):
    # runtime_switchable_config
    arg = f"""<key>{key}</key>
    <source_file>ms-appdata:///local/RSC.bin</source_file>"""
    cmd = create_cmd("SET-RSC", arg)
    return cmd


def cmd_write_private_cert():
    arg = f"""<source_file>ms-appdata:///local/cert.bin</source_file>"""
    cmd = create_cmd("WRITE-PRIVATE-CERT", arg)
    return cmd


def cmd_get_da_info(mem_offset:int=0x2000000, mem_length:int=0x20000):
    arg=f"""<target_file>MEM://{hex(mem_offset)}:{hex(mem_length)}</target_file>"""
    cmd = create_cmd("GET-DA-INFO", arg)
    resp="""
    <?xml version=\"1.0\" encoding=\"utf-8\"?><host><version>1.0</version><command>CMD:UPLOAD-FILE</command><arg><checksum>CHK_NO</checksum><info>WriteLocalFile</info><target_file>%s</target_file><packet_length>0x%x</packet_length></arg></host>
    <?xml version=\"1.0\" encoding=\"utf-8\"?><da_info><version>1.0</version><da_version>2021</da_version><build>May 24 2022:19:03:56</build></da_info>"
    OK
    OK@0x%x
    """
    return cmd

def cmd_set_host_info(hostinfo:str="2002.02.03T11.22.33-PC11123445"):
    arg=f"""<info>{hostinfo}</info>"""
    cmd = create_cmd("SET-HOST-INFO", arg)
    return cmd


def cmd_get_downloaded_image_feedback(mem_offset:int=0x2000000, mem_length:int=0x20000):
    arg=f"""<target_file>MEM://{hex(mem_offset)}:{hex(mem_length)}</target_file>"""
    cmd = create_cmd("GET-DOWNLOADED-IMAGE-FEEDBACK", arg)
    return cmd



