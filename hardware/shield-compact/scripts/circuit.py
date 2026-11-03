"""Compact Shield circuit and nominal placement. Run KiCad generators on the build host.

Pin numbers below are physical package/module numbers, not GPIO numbers.
Sources and independent checks live in sources.json and check_compact_shield.py.
"""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parents[1]
REV = json.loads((HERE / 'revision.json').read_text())
PARTS = []


def part(ref, value, footprint, xy, nets, names=None, types=None, angle=0,
         side='front', mpn='', datasheet='', section='Logic', dnp=False):
    nets = {str(k): v for k, v in nets.items()}
    p = dict(ref=ref, value=value, footprint=footprint, x=xy[0], y=xy[1],
             rotation=angle, side=side, nets=nets,
             names={str(k): v for k, v in (names or {}).items()},
             pin_types={str(k): v for k, v in (types or {}).items()},
             mpn=mpn or value, datasheet=datasheet, section=section, dnp=dnp)
    PARTS.append(p)
    return p


def r(ref, val, xy, a, b, angle=0, dnp=False):
    return part(ref, val, 'Resistor_SMD:R_0603_1608Metric', xy,
                {1:a, 2:b}, angle=angle, section='Passives', dnp=dnp)


def c(ref, val, xy, net, ground='GND', angle=0, large=False):
    return part(ref, val, 'Capacitor_SMD:C_1206_3216Metric' if large else
                'Capacitor_SMD:C_0603_1608Metric', xy,
                {1:net, 2:ground}, angle=angle, section='Decoupling')


def header(ref, value, xy, nets, labels, angle=0, pitch=2.0, keyed=True, dnp=False):
    n=len(nets)
    fp=(f'Connector_JST:JST_PH_B{n}B-PH-K_1x{n:02d}_P2.00mm_Vertical'
        if keyed else f'Connector_PinHeader_2.54mm:PinHeader_1x{n:02d}_P2.54mm_Vertical')
    return part(ref, value, fp, xy, dict(enumerate(nets, 1)),
                dict(enumerate(labels, 1)), angle=angle, side='back', section='Connectors', dnp=dnp)


GPIO_NET = {0:'BOOT',1:'EXT1',2:'EXT2',3:'STRAP3',4:'TC_DO',5:'GPIO5',
  6:'TC_SCK',7:'TC_CS',8:'EXT3',9:'PUMP_PWM',10:'VALVE',11:'BOARD_ID',
  12:'EXT4',13:'EXT5',14:'HEATER',15:'GPIO15',16:'GPIO16',17:'SCALE_CLK',
  18:'SCALE_DAT0',19:'USB_DM_MCU',20:'USB_DP_MCU',21:'PUMP_ZC',
  38:'BREW',39:'SCALE_DAT1',40:'DETECT_EN',41:'SCL_3V3',42:'SDA_3V3',
  43:'ALBA_SDA',44:'ALBA_SCL',45:'STRAP45',46:'STRAP46',47:'ALT',48:'STEAM'}
WROOM_GPIO = {4:4,5:5,6:6,7:7,8:15,9:16,10:17,11:18,12:8,13:19,14:20,
  15:3,16:46,17:9,18:10,19:11,20:12,21:13,22:14,23:21,24:47,25:48,
  26:45,27:0,28:35,29:36,30:37,31:38,32:39,33:40,34:41,35:42,36:44,
  37:43,38:2,39:1}
u1={1:'GND',2:'+3V3',3:'EN',40:'GND',41:'GND'}
u1.update({pin:GPIO_NET.get(gpio) for pin,gpio in WROOM_GPIO.items()})
names={pin:f'GPIO{gpio}' for pin,gpio in WROOM_GPIO.items()}
names.update({1:'GND',2:'3V3',3:'EN',40:'GND',41:'EP_GND'})
types={pin:'bidirectional' for pin in WROOM_GPIO}
types.update({1:'power_in',2:'power_in',3:'input',40:'power_in',41:'power_in'})
part('U1','ESP32-S3-WROOM-1-N16R8','RF_Module:ESP32-S3-WROOM-1',(15,6.35),
     u1,names,types,mpn='ESP32-S3-WROOM-1-N16R8',section='MCU',
     datasheet='https://documentation.espressif.com/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf')

# USB and core power. The external bus never receives USB VBUS through the OR.
usb={k:'GND' for k in ['A1','A12','B1','B12','SH']}
usb.update({k:'USB_VBUS' for k in ['A4','A9','B4','B9']})
usb.update({'A5':'CC1','B5':'CC2','A6':'USB_DP','B6':'USB_DP',
            'A7':'USB_DM','B7':'USB_DM','A8':None,'B8':None})
part('J_USB','USB4085-GF-A','Connector_USB:USB_C_Receptacle_GCT_USB4085',
     (4.5,50.865),usb,section='USB',datasheet='https://gct.co/connector/usb4085')
r('R_CC1','5.1k 1%',(14,41),'CC1','GND',90)
r('R_CC2','5.1k 1%',(17,41),'CC2','GND',90)
r('R_USBP','22R 1%',(3.5,20.5),'USB_DP_MCU','USB_DP',90)
r('R_USBM','22R 1%',(3.5,17),'USB_DM_MCU','USB_DM',90)
part('U_ESD','USBLC6-2SC6','Package_TO_SOT_SMD:SOT-23-6',(13.5,44),
     {1:'USB_DM',2:'GND',3:'USB_DP',4:'USB_DP',5:'USB_VBUS',6:'USB_DM'},
     section='USB',datasheet='https://www.st.com/resource/en/datasheet/usblc6-2.pdf')
part('F_USB','1206L050YR 0.5A','Fuse:Fuse_1206_3216Metric',(17,46.5),
     {1:'USB_VBUS',2:'USB_FUSED'},section='Power')
part('F_EXT','1206L150/12 1.5A','Fuse:Fuse_1206_3216Metric',(46,3.5),
     {1:'EXT_IN',2:'+5V_EXT'},section='Power')
for ref,xy,anode in [('D_USB',(22,46.5),'USB_FUSED'),('D_EXT',(37,7.5),'+5V_EXT')]:
    part(ref,'SS14','Diode_SMD:D_SMA',xy,{1:'+5V_CORE',2:anode},
         {1:'K',2:'A'},section='Power')
part('U_REG','AP7361C-33E-13','Package_TO_SOT_SMD:SOT-223-3_TabPin2',(45,9),
     {1:'+5V_CORE',2:'GND',3:'+3V3'}, {1:'IN',2:'GND_TAB',3:'OUT'},
     {1:'power_in',2:'power_in',3:'power_out'},section='Power',
     datasheet='https://www.diodes.com/datasheet/download/AP7361C.pdf')
c('C_IN','10uF 16V X7R',(37.5,10.5),'+5V_CORE',large=True)
c('C_OUT','10uF 16V X7R',(51,8),'+3V3',large=True)
c('C_MCU','10uF 16V X7R',(3,7.5),'+3V3',angle=90,large=True)
c('C_MCUHF','100nF 50V X7R',(3,2.5),'+3V3',angle=180)
r('R_EN','10k 1%',(4,11.5),'+3V3','EN')
c('C_EN','1uF 16V X7R',(4,14),'EN')
r('R_BOOT','10k 1%',(27,17),'+3V3','BOOT')
for ref,label,xy,net in [('SW_RESET','RESET',(34,17),'EN'),('SW_BOOT','BOOT',(40,17),'BOOT')]:
    part(ref,label,'Button_Switch_SMD:SW_SPST_TL3342',xy,
         {1:net,2:'GND'},section='Boot')
r('R_ID_TOP','10k 1%',(26.5,10),'DETECT_EN','BOARD_ID')
r('R_ID_LOW','1.62k 1%',(30.5,10),'BOARD_ID','GND')
c('C_ID','10nF 50V C0G',(30.5,13),'BOARD_ID')

c('C_LVA','100nF 50V X7R',(71,51),'+3V3')
c('C_LVB','100nF 50V X7R',(79,51),'+5V_CORE')
part('J_ADS','ADS1115 BLUE SOCKET','GemilaiMateCompact:ADS1115_socket',(23,24.14),
     dict(enumerate(['+5V_CORE','GND','SCL_5V','SDA_5V','GND',None,'PRESSURE',None,None,None],1)),
     dict(enumerate(['VDD','GND','SCL','SDA','ADDR','ALRT','A0','A1','A2','A3'],1)),angle=270,section='ADC',
     mpn='M20-7821046')
r('R_PRESS','1k 1%',(23,41),'PRESSURE_RAW','PRESSURE')
c('C_PRESS','100nF 50V X7R',(25.5,44),'PRESSURE')
part('J_TC','MAX31855 SOCKET','GemilaiMateCompact:MAX31855_socket',(56.5,24),
     dict(enumerate(['TC_VIN',None,'GND','TC_DO','TC_CS','TC_SCK'],1)),
     dict(enumerate(['VIN','3Vo_NC','GND','DO','CS','CLK'],1)),section='Temperature',
     mpn='M20-7820646')

# ZC input: 5.5 V tolerant, non-inverting, with an external pull-up.
r('R_ZCPU','10k 1%',(34.5,43),'+5V_EXT','ZC_RAW')
r('R_ZCS','1k 1%',(39,43),'ZC_RAW','ZC_IN')
part('U_ZC','SN74LVC1G17DBVR','Package_TO_SOT_SMD:SOT-23-5',(38,34),
     {1:None,2:'ZC_IN',3:'GND',4:'PUMP_ZC',5:'+3V3'},
     {1:'NC',2:'A',3:'GND',4:'Y',5:'VCC'},
     {2:'input',3:'power_in',4:'output',5:'power_in'},section='Pump',
     datasheet='https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf')
c('C_ZC','100nF 50V X7R',(37,31),'+3V3')

# Buffers are disabled while EXT is absent. This is independent of firmware.
r('R_EXT_BASE','47k 1%',(53,46),'+5V_EXT','EXT_BASE')
r('R_EXT_PD','100k 1%',(57,46),'EXT_BASE','GND')
part('Q_EXT','MMBT3904','Package_TO_SOT_SMD:SOT-23',(48.5,45),
     {1:'EXT_BASE',2:'GND',3:'OUTPUT_OE_N'}, {1:'B',2:'E',3:'C'},section='Outputs')
r('R_OEUP','10k 1%',(44,45),'+3V3','OUTPUT_OE_N')
part('U_PUMP','SN74LVC1G125DBVR','Package_TO_SOT_SMD:SOT-23-5',(41.5,38),
     {1:'OUTPUT_OE_N',2:'PUMP_PWM',3:'GND',4:'PUMP_OUT',5:'+3V3'},
     {1:'OE_N',2:'A',3:'GND',4:'Y',5:'VCC'},
     {1:'input',2:'input',3:'power_in',4:'tri_state',5:'power_in'},section='Outputs',
     datasheet='https://www.ti.com/lit/ds/symlink/sn74lvc1g125.pdf')
part('U_SSR','SN74AHCT125PWR','Package_SO:TSSOP-14_4.4x5mm_P0.65mm',(53,33),
     {1:'OUTPUT_OE_N',2:'VALVE',3:'VALVE_5V',4:'OUTPUT_OE_N',5:'HEATER',6:'HEATER_5V',
      7:'GND',8:'ALT_5V',9:'ALT',10:'OUTPUT_OE_N',11:None,12:'GND',13:'+5V_EXT',14:'+5V_EXT'},
     {1:'1OE_N',2:'1A',3:'1Y',4:'2OE_N',5:'2A',6:'2Y',7:'GND',8:'3Y',9:'3A',10:'3OE_N',11:'4Y_NC',12:'4A',13:'4OE_N',14:'VCC'},
     {1:'input',2:'input',3:'tri_state',4:'input',5:'input',6:'tri_state',7:'power_in',
      8:'tri_state',9:'input',10:'input',11:'tri_state',12:'input',13:'input',14:'power_in'},
     section='Outputs',datasheet='https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf')
c('C_SSR','100nF 50V X7R',(58,31),'+5V_EXT')
c('C_PUMP','100nF 50V X7R',(45,38),'+3V3')
for i,(net,xy) in enumerate([('PUMP_PWM',(26,20)),('VALVE',(32,20)),('HEATER',(37,20)),('ALT',(41.5,20)),('PUMP_OUT',(40,46))],1):
    r('R_PD'+str(i),'10k 1%',xy,net,'GND')

for tag,xy in [('VALVE',(48,30)),('HEATER',(48,33)),('ALT',(48,36))]:
    r('R_OUT_'+tag,'10k 1%',xy,tag+'_5V','GND')

# Dry-contact inputs, same active-low contract as upstream.
for tag,xy,net in [('BREW',(21,33),'BREW'),('STEAM',(21,29),'STEAM')]:
    r('R_'+tag,'1k 1%',xy,net+'_RAW',net)
    r('R_'+tag+'PU','10k 1%',(xy[0]-4,xy[1]),'+3V3',net)
    c('C_'+tag,'100nF 50V X7R',(xy[0]-8,xy[1]),net)

# PCA9634 address 0x00, as used by the original firmware. General-call users
# must not be added to this closed bus without reviewing address conflicts.
pca={1:'GND',2:'GND',3:'GND',4:'GND',5:'GND',6:'PCA_LED0',7:'PCA_LED1',8:'PCA_LED2',9:'PCA_LED3',10:'GND',
     11:'PCA_LED4',12:'PCA_LED5',13:'PCA_LED6',14:'PCA_LED7',15:'GND',16:'GND',17:'GND',18:'PCA_SCL',19:'PCA_SDA',20:'+3V3'}
pca_names={1:'A0',2:'A1',3:'A2',4:'A3',5:'A4',6:'LED0',7:'LED1',8:'LED2',9:'LED3',10:'VSS',
           11:'LED4',12:'LED5',13:'LED6',14:'LED7',15:'OE_N',16:'A5',17:'A6',18:'SCL',19:'SDA',20:'VDD'}
pca_types={pin:('power_in' if pin in (10,20) else 'bidirectional' if pin==19 else
                'open_collector' if pin in (6,7,8,9,11,12,13,14) else 'input') for pin in pca}
part('U_LED','PCA9634PW','Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm',(51,18),pca,pca_names,pca_types,
     section='Alba',datasheet='https://www.nxp.com/docs/en/data-sheet/PCA9634.pdf')
r('R_PCACLK','0R',(44,24),'ALBA_SCL','PCA_SCL')
r('R_PCADAT','0R',(49,26),'ALBA_SDA','PCA_SDA')
c('C_PCA','100nF 50V X7R',(57,17.5),'+3V3')
r('R_ALBASDA','4.7k 1%',(30,22.5),'+3V3','ALBA_SDA')
r('R_ALBASCL','4.7k 1%',(36,23),'+3V3','ALBA_SCL')
for ch,xy in enumerate([(56,6),(56,9),(56,12),(56,15)]):
    r('R_LED'+str(ch),'180R 1%',xy,'PCA_LED'+str(ch),'RGBW'+str(ch))
for ch,xy in [(4,(59,41)),(5,(59,36))]:
    r('R_GATE'+str(ch),'100R 1%',(xy[0]-4,xy[1]),'PCA_LED'+str(ch),'LED_GATE'+str(ch))
    r('R_GPD'+str(ch),'100k 1%',(xy[0]-4,xy[1]+2.5),'LED_GATE'+str(ch),'GND')
    part('Q_LED'+str(ch),'AO3400A','Package_TO_SOT_SMD:SOT-23',xy,
         {1:'LED_GATE'+str(ch),2:'GND',3:'LED'+str(ch)+'_DRAIN'},
         {1:'G',2:'S',3:'D'},section='Alba')

# Supply input is the only JST XH: no PH plug of this board mates with it, and
# the PSU plug cannot enter the PH display port that bypasses F_EXT.
part('J_PWR','5V INPUT','Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',(61,18),
     {1:'EXT_IN',2:'GND'},{1:'5V_IN',2:'GND'},angle=90,side='back',section='Connectors')
header('J_DISPLAY','DISPLAY 5V',(52,3),['+5V_EXT','GND'],['5V_EXT','GND'],angle=180)
header('J_PRESS','PRESSURE',(20,47),['+5V_EXT','GND','PRESSURE_RAW'],['5V','GND','OUT'])
header('J_BUTTONS','BUTTONS',(26,47),['BREW_RAW','STEAM_RAW','GND','GND'],['BREW','STEAM','GND','GND'])
# Six positions, the only PH-6 on the board: the RobotDyn plug cannot enter the
# 4-pin I2C ports, where SCL would drive PSM. Positions 5/6 stay empty.
header('J_PUMP','ROBOTDYN',(37,48),['+5V_EXT','GND','ZC_RAW','PUMP_OUT',None,None],['5V','GND','ZC','PSM','EMPTY','EMPTY'],angle=180)
header('J_VALVE','VALVE SSR',(63,32),['+5V_EXT','GND','VALVE_5V'],['5V','GND','IN'],angle=90)
header('J_HEAT','HEATER UNUSED',(52,41),['+5V_EXT','GND','HEATER_5V'],['5V','GND','IN'],angle=180,dnp=True)
header('J_ALT','ALT SSR',(49,48),['+5V_EXT','GND','ALT_5V'],['5V','GND','IN'],angle=180)
# External I2C is 3.3 V only. The 470R series resistors are not level shifters
# and do not make these GPIO inputs 5 V tolerant.
header('J_TOF','VL53L0X 3V3',(34,36),['+3V3','GND','EXT_SDA','EXT_SCL'],['3V3','GND','SDA','SCL'],angle=90)
# External Alba lights load the external 5 V bus, not the LDO/ADS/TXS core rail.
header('J_ALBA','EXTERNAL ALBA',(63,24),['+5V_EXT','GND','EXT_SDA','EXT_SCL'],['5V_EXT','GND','SDA','SCL'],angle=90)
header('J_RGBW','RGBW CA',(63,12),['+5V_EXT','RGBW0','RGBW1','RGBW2','RGBW3'],['5V_CA','R','G','B','W'],angle=90)
header('J_LIGHT','LIGHTS 200mA TOTAL',(63,44),['+5V_EXT','LED4_DRAIN','LED5_DRAIN'],['5V','CH4_NEG','CH5_NEG'],angle=90)
part('J_SCALE','SCALE 3V3','Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical',(32,40),
     {1:'+3V3',2:'GND',3:'SCALE_CLK',4:'SCALE_DAT0',5:'SCALE_DAT1'},angle=90,section='Expansion',dnp=True)
part('J_EXT','EXT 3V3','Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical',(33,25),
     {1:'+3V3',2:'GND',3:'EXT1',4:'EXT2',5:'EXT3',6:'EXT4',7:'EXT5',8:'+5V_EXT',9:'GND',10:'GND'},
     section='Expansion',dnp=True)
part('J_FREE','FREE GPIO 3V3','Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',(32,12.5),
     {1:'+3V3',2:'GND',3:'GPIO5',4:'GPIO15',5:'GPIO16',6:'GND'},angle=90,section='Expansion',dnp=True)
# Keep the legacy cable connector designators stable; this inserted module socket
# is appended after the existing J1-J18 connectors.
part('J_LEVEL','CJMCU-0102 TXS0102 SOCKET','GemilaiMateCompact:CJMCU0102_socket',(41,12.5),
     {1:'GND',2:'+3V3',3:'+3V3',4:'SCL_3V3',5:'SDA_3V3',
      6:'GND',7:None,8:'+5V_CORE',9:'SCL_5V',10:'SDA_5V'},
     {1:'GND_A',2:'OE',3:'VCCA',4:'A1',5:'A2',
      6:'GND_B',7:'G_RESERVED_NC',8:'VCCB',9:'B1',10:'B2'},
     {1:'power_in',2:'input',3:'power_in',4:'bidirectional',5:'bidirectional',
      6:'power_in',8:'power_in',9:'bidirectional',10:'bidirectional'},
     section='ADC',mpn='2 x Harwin M20-7820546')
for i,(net,xy) in enumerate([('STRAP3',(28,14)),('STRAP45',(26,8)),('STRAP46',(29,8)),
                            ('BOOT',(31,18)),('+3V3',(34,11)),('GND',(34,7)),
                            ('ALBA_SDA',(26,24)),('ALBA_SCL',(27,26)),
                            ('PCA_LED6',(48,12)),('PCA_LED7',(51,12))],1):
    part('TP'+str(i),net,'TestPoint:TestPoint_Pad_D1.0mm',xy,{1:net},section='Testpoints',dnp=True)

# Transient clamp only. The TVS and PTC are not reverse-polarity or sustained
# over-voltage protection; require a correctly polarized regulated 5 V supply.
part('D_TVS','SMAJ5.0A','Diode_SMD:D_SMA',(43,6),{1:'+5V_EXT',2:'GND'},{1:'K',2:'A'},
     section='Power',datasheet='https://www.littelfuse.com/products/tvs-diodes/surface-mount/smaj')
c('C_EXT','10uF 16V X7R',(41,3),'+5V_EXT',large=True)
# Series resistors for the off-board I2C ports J_TOF / J_ALBA.
r('R_EXTSDA','470R 1%',(33,30),'ALBA_SDA','EXT_SDA')
r('R_EXTSCL','470R 1%',(33,32),'ALBA_SCL','EXT_SCL')
# MAX31855 VIN defaults to 3.3 V, safe for bare and regulated breakouts and never
# lets 5 V logic reach the ESP32. 5 V needs a deliberate 0R swap, not a loose jumper.
r('R_TC3V3','0R',(36,40),'+3V3','TC_VIN')
r('R_TC5V','0R',(36,42),'+5V_CORE','TC_VIN',dnp=True)

# Numeric KiCad designators; logical aliases remain stable for generators and
# readable connection tables, independently of physical placement.
from collections import defaultdict
_counts=defaultdict(int)
for component in PARTS:
    alias=component['ref']
    prefix='TP' if alias.startswith('TP') else 'SW' if alias.startswith('SW') else 'JP' if alias.startswith('JP') else alias[0]
    _counts[prefix]+=1
    component['designator']=prefix+str(_counts[prefix])

# Procurement examples; substitute only after checking value, dielectric,
# voltage and the exact package. No marketplace seller is implied by an MPN.
_res={'5.1k 1%':'5K1L','22R 1%':'22RL','10k 1%':'10KL','1.62k 1%':'1K62L','1k 1%':'1KL',
      '100k 1%':'100KL','47k 1%':'47KL','4.7k 1%':'4K7L','180R 1%':'180RL','100R 1%':'100RL','470R 1%':'470RL'}
_caps={'10uF 16V X7R':'GRM31CR71C106KAC7L','100nF 50V X7R':'GRM188R71H104KA93D',
       '1uF 16V X7R':'GRM188R71C105KA12D','10nF 50V C0G':'GRM1885C1H103JA01D'}
for component in PARTS:
    ref=component['ref'];v=component['value']
    if ref.startswith('R'):component['mpn']='RC0603FR-07'+_res[v] if v!='0R' else 'RC0603JR-070RL'
    if ref.startswith('C'):component['mpn']=_caps[v]
    if ref.startswith('SW_'):component['mpn']='TL3342F160QG'
    if ref.startswith('D_'):component['mpn']='SMAJ5.0A' if ref=='D_TVS' else 'SS14-13-F'
    if ref=='U_LED':component['mpn']='PCA9634PW,118'
    if ref=='F_USB':component['mpn']='1206L050YR'
    if ref=='F_EXT':component['mpn']='1206L150/12SLYR'
    if ref=='Q_EXT':component['mpn']='MMBT3904-7-F'
    if ref=='J_PWR':component['mpn']='B2B-XH-A(LF)(SN)'
    if ref.startswith('J_') and ref not in ['J_PWR','J_ADS','J_TC'] and component['footprint'].split(':')[-1].startswith('JST_PH_B'):
        n=len(component['nets'])
        component['mpn']=f'B{n}B-PH-K-S(LF)(SN)'

SPEC = dict(project='GemilaiMate Modular Shield', revision=REV['revision'], date=REV['date'],
            size_mm=[75,60], copper_layers=4, author='Rico-X',
            repository='https://github.com/Rico-X/GemilaiMate',
            hardware_tested=False, manufacturing_release=False, mains_on_board=False,
            board_id=4, physical_flash_mb=16, compatible_partition_flash_mb=8,
            psram_mb=8, peripheral_gpio={'sda':43,'scl':44},
            rf_keepout=[5.5,-8,24.5,-.1],
            module_body=[6,-7.15,24,18.35],
            mounts_mm=[[3,3],[72,3],[17,57.5],[72,57]],
            firmware_target='controller-compact', parts=PARTS)

if __name__ == '__main__':
    (HERE/'circuit.json').write_text(json.dumps(SPEC,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(PARTS)} components, {len(set(n for p in PARTS for n in p["nets"].values() if n))} nets')
