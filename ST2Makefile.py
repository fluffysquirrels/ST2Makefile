#!/usr/bin/env python

import sys
import re
import shutil
import os.path
from string import Template
from xml.etree import ElementTree as ET


def replace_path(text):
    dict = {
        "PARENT-1-PROJECT_LOC" : "..",
        "PARENT-2-PROJECT_LOC" : "../..",
        "PARENT-3-PROJECT_LOC" : "../../..",
        "PARENT-4-PROJECT_LOC" : "../../../..",
        "PARENT-5-PROJECT_LOC" : "../../../../.."
    } 
    # Create a regular expression  from the dictionary keys
    regex = re.compile("(%s)" % "|".join(map(re.escape, dict.keys())))
    # For each match, look-up corresponding value in dictionary
    return regex.sub(lambda mo: dict[mo.string[mo.start():mo.end()]], text)
     

T2M_ERR_SUCCESS             =  0
T2M_ERR_INVALID_COMMANDLINE = -1
T2M_ERR_LOAD_TEMPLATE       = -2
T2M_ERR_NO_PROJECT          = -3
T2M_ERR_PROJECT_FILE        = -4
T2M_ERR_IO                  = -5
T2M_ERR_NEED_UPDATE         = -6

# STM32 part to compiler flag mapping
mcu_cflags = {}
mcu_cflags[re.compile('STM32(F|L)0')] = '-mthumb -mcpu=cortex-m0'
mcu_cflags[re.compile('.*Cortex-M0')] = '-mthumb -mcpu=cortex-m0'
mcu_cflags[re.compile('STM32(F|L)1')] = '-mthumb -mcpu=cortex-m3'
mcu_cflags[re.compile('STM32(F|L)2')] = '-mthumb -mcpu=cortex-m3'
mcu_cflags[re.compile('STM32(F|L)3')] = '-mthumb -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=softfp'
mcu_cflags[re.compile('STM32(F|L)4')] = '-mthumb -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=softfp'

# Set use_project_ld_script = True to use the LD script the TrueSTUDIO project specifies
# Set use_project_ld_script = False to use the template .ld script from ST2Makefile.
use_project_ld_script = True

if len(sys.argv) != 2:
    sys.stderr.write("\r\nTrueSTUDIO STM32 project to Makefile V1.0\r\n")
    sys.stderr.write("-==================================-\r\n")
    sys.stderr.write("Written by Baoshi <mail\x40ba0sh1.com> on 2015-04-30\r\n")
    sys.stderr.write("Copyright www.ba0sh1.com\r\n")
    sys.stderr.write("Apache License 2.0 <http://www.apache.org/licenses/LICENSE-2.0>\r\n")
    sys.stderr.write("Usage:\r\n")
    sys.stderr.write("  ST2Makefile.py <TrueSTUDIO project folder>\r\n")
    sys.exit(T2M_ERR_INVALID_COMMANDLINE)

# Load template files
app_folder = os.path.dirname(os.path.abspath(sys.argv[0]))
try:
    fd = open(app_folder + os.path.sep + 'Makefile.tpl', 'rb')
    mft = Template(fd.read())
    fd.close()
except:
    sys.stderr.write("Unable to load template file Makefile.tpl\r\n")
    sys.exit(T2M_ERR_LOAD_TEMPLATE)

try:
    fd = open(app_folder + os.path.sep + 'Link.tpl', 'rb')
    ldt = Template(fd.read())
    fd.close()
except:
    sys.stderr.write("Unable to load template file Link.tpl\r\n")
    sys.exit(T2M_ERR_LOAD_TEMPLATE)

proj_folder = os.path.abspath(sys.argv[1])
if not os.path.isdir(proj_folder):
    sys.stderr.write("TrueSTUDIO project folder %s not found\r\n" % proj_folder)
    sys.exit(T2M_ERR_INVALID_COMMANDLINE)
    
proj_name = os.path.splitext(os.path.basename(proj_folder))[0].replace(' ', '_')
ts_project = proj_folder + os.path.sep + '.project'
ts_cproject = proj_folder + os.path.sep + '.cproject'
if not (os.path.isfile(ts_project) and os.path.isfile(ts_cproject)):
    sys.stderr.write("TrueSTUDIO project not found. Please make sure \".project\" and \".cproject\" are inside project folder.\r\n")
    sys.exit(T2M_ERR_NO_PROJECT)

# .project file
try:
    tree = ET.parse(ts_project)
    root = tree.getroot()
except Exception, e:
    sys.stderr.write("Error: cannot parse TrueSTUDIO .project file: %s\r\n" % ts_project)
    sys.exit(T2M_ERR_PROJECT_FILE)
nodes = root.findall('linkedResources/link[type=\'1\']/locationURI')
sources = []
for node in nodes:
    sources.append(replace_path(node.text))
sources=list(set(sources))
sources.sort()
c_sources = 'C_SOURCES ='
asm_sources = 'ASM_SOURCES ='
a_files = ''
for source in sources:
    ext = os.path.splitext(source)[1]
    if ext == '.c':
        c_sources += ' \\\n  ' + source
    elif ext == '.s':
        asm_sources = asm_sources + ' \\\n  ' + source
    elif ext == '.a':
        a_files = a_files + ' \\\n  ' + source
    else:
        sys.stderr.write("Unknown source file type: %s\r\n" % source)
        sys.exit(-5)
# .cproject file
try:
    tree = ET.parse(ts_cproject)
    root = tree.getroot()
except Exception, e:
    sys.stderr.write("Error: cannot parse TrueSTUDIO .cproject file: %s\r\n" % ts_cproject)
    sys.exit(T2M_ERR_PROJECT_FILE)
# MCU
mcu = ''
node = root.find('.//tool[@superClass="com.atollic.truestudio.exe.release.toolchain.as"]/option[@name="Microcontroller"]')
try:
    value = node.attrib.get('value')
except Exception, e:
    sys.stderr.write("No target MCU defined\r\n")
    sys.exit(T2M_ERR_PROJECT_FILE)
for pattern, option in mcu_cflags.items():
    if pattern.match(value):
        mcu = option
if (mcu == ''):
    sys.stderr.write("Unknown MCU\r\n, please contact author for an update of this utility\r\n")
    sys.stderr.exit(T2M_ERR_NEED_UPDATE)
# AS include
as_includes = 'AS_INCLUDES ='
nodes = root.findall('.//tool[@superClass="com.atollic.truestudio.exe.release.toolchain.as"]/option[@valueType="includePath"]/listOptionValue')
first = 1
for node in nodes:
    value = node.attrib.get('value')
    if (value != ""):
        value = re.sub(r'^..(\\|/)..(\\|/)..(\\|/)', '', value.replace('\\', os.path.sep))
        if first:
            as_includes = 'AS_INCLUDES = -I' + value
            first = 0
        else:
            as_includes += '\nAS_INCLUDES += -I' + value
# AS symbols
as_defs = 'AS_DEFS ='
nodes = root.findall('.//tool[@superClass="com.atollic.truestudio.exe.release.toolchain.as"]/option[@valueType="definedSymbols"]/listOptionValue')
for node in nodes:
    value = node.attrib.get('value')
    if (value != ""):
        as_defs += ' -D' + value
# C include
c_includes = 'C_INCLUDES ='
nodes = root.findall('.//tool[@superClass="com.atollic.truestudio.exe.release.toolchain.gcc"]/option[@valueType="includePath"]/listOptionValue')
first = 1
for node in nodes:
    value = node.attrib.get('value')
    if (value != ""):
        value = re.sub(r'^..(\\|/)', '', value.replace('\\', os.path.sep)) # up one level
        if first:
            c_includes = 'C_INCLUDES = -I' + value
            first = 0
        else:
            c_includes += '\nC_INCLUDES += -I' + value
# C symbols
c_defs = 'C_DEFS ='
nodes = root.findall('.//tool[@superClass="com.atollic.truestudio.exe.release.toolchain.gcc"]/option[@valueType="definedSymbols"]/listOptionValue')
for node in nodes:
    value = node.attrib.get('value')
    if (value != ""):
        c_defs += ' -D' + value

# Link script
memory = ''
estack = ''
node = root.find('.//tool[@superClass="com.atollic.truestudio.exe.release.toolchain.ld"]/option[@superClass="com.atollic.truestudio.ld.general.scriptfile"]')
project_ld_path = ''
try:
    value = node.attrib.get('value')
    project_ld_path = re.sub(r'^..(\\|/)', '', value.replace('\\', os.path.sep))
    ld_script = proj_folder + os.path.sep + project_ld_path
    fd = open(ld_script, 'r')
    ls = fd.read()
    fd.close()
    p = re.compile(ur'MEMORY(\n|\r\n|\r)?{(\n|\r\n|\r)?(.*?)(\n|\r\n|\r)?}', re.DOTALL | re.IGNORECASE)
    m = re.search(p, ls)
    if m:
        memory = m.group(3)
    p = re.compile(ur'(_estack.*)')
    m = re.search(p, ls)
    if m:
        estack = m.group(1)
except Exception, e:
    sys.stderr.write("Unable to find or read link script from TrueSTUDIO project file\r\n")
    sys.exit(T2M_ERR_IO)
if ((memory =='') | (estack == '')):
    sys.stderr.write("Unable to locate memory layout from link script\r\n")
    sys.exit(T2M_ERR_NEED_UPDATE)

if use_project_ld_script:
    ld_path = project_ld_path
else:
    ld_path = 'arm-gcc-link.ld'

mf = mft.substitute( \
    TARGET = proj_name, \
    MCU = mcu, \
    C_SOURCES = c_sources, \
    ASM_SOURCES = asm_sources, \
    AS_DEFS = as_defs, \
    AS_INCLUDES = as_includes, \
    C_DEFS = c_defs, \
    C_INCLUDES = c_includes, \
    LD_PATH = ld_path, \
    A_FILES = a_files)
try:
    fd = open(proj_folder + os.path.sep + 'Makefile', 'wb')
    fd.write(mf)
    fd.close()
except:
    sys.stderr.write("Write Makefile failed\r\n")
    sys.exit(T2M_ERR_IO)
sys.stdout.write("File created: %s\r\n" % (proj_folder + os.path.sep + 'Makefile'))

if not use_project_ld_script:
    ld = ldt.substitute( \
        MEMORY = memory, \
        ESTACK = estack)
    try:
        fd = open(proj_folder + os.path.sep + 'arm-gcc-link.ld', 'wb')
        fd.write(ld)
        fd.close()
    except:
        sys.stderr.write("Write link script failed\r\n")
        sys.exit(T2M_ERR_IO)
    sys.stdout.write("File created: %s\r\n" % (proj_folder + os.path.sep + 'arm-gcc-link.ld'))

sys.exit(T2M_ERR_SUCCESS)
