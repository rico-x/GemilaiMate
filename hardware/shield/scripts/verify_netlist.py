import json,re
from pathlib import Path
import sexpdata
import os
out=Path(__file__).resolve().parents[1]
source_root=Path(os.environ.get('GEMILAIMATE_FIRMWARE', str(out.parents[1]/'firmware')))
spec=json.loads((out/'design.json').read_text())
t=sexpdata.loads((out/'gemilaimate-shield.net').read_text())
get=lambda x,k:next((a[1:] for a in x if isinstance(a,list) and str(a[0])==k),[])
netnodes={}; mapping={}
for n in get(t,'nets'):
 name=get(n,'name')[0];nodes=[]
 for a in n:
  if isinstance(a,list) and str(a[0])=='node':
   ref=get(a,'ref')[0];pin=str(get(a,'pin')[0]);nodes.append((ref,pin));mapping[ref+'.'+pin]=name
 netnodes[name]=set(nodes)
expected={}
for c in spec['parts']:
 for pin in c['pins']:
  if pin['net']:expected.setdefault('/'+pin['net'],set()).add((c['ref'],pin['number']))
assert {k:v for k,v in netnodes.items() if not k.startswith('unconnected-')}==expected
assert all(len(v)==1 for k,v in netnodes.items() if k.startswith('unconnected-'))
(out/'schematic-pad-nets.json').write_text(json.dumps(mapping,indent=2))

# Independent comparison against the pinned firmware configuration, rather
# than merely comparing two files generated from the same placement data.
source=(source_root/'lib/GemilaiMateController/src/ControllerConfig.h').read_text()
block=source.split('const ControllerConfig GEMILAI_3007Z =',1)[1].split('const ControllerConfig',1)[0]
actual={k:int(v) for k,v in re.findall(r'\.(\w+)\s*=\s*(\d+)',block)}
functions={'pumpPin':'PUMP_PWM','pumpSensePin':'PUMP_ZC','valvePin':'VALVE_3V3','heaterPin':'HEATER_3V3','pressureScl':'SCL_3V3','pressureSda':'SDA_3V3','maxSckPin':'TC_SCK','maxCsPin':'TC_CS','maxMisoPin':'TC_DO','brewButtonPin':'BREW','steamButtonPin':'STEAM'}
mcu=next(x for x in spec['parts'] if x['ref']=='U1')
verified={}
for field,nn in functions.items():
 pin=next(x for x in mcu['pins'] if x['net']==nn)
 number=int(pin['name'].replace('GPIO',''))
 assert number==actual[field],(field,number,actual[field])
 verified[field]={'gpio':number,'carrier_pin':'U1.'+pin['number'],'net':nn}
assert all(x['net'] is None for x in mcu['pins'] if x['name'].endswith('_RESERVED'))
header=(source_root/'lib/GemilaiMateController/src/GemilaiMateController.h').read_text()
for field,nn in [('DETECT_EN_PIN','DETECT_EN'),('DETECT_VALUE_PIN','BOARD_ID')]:
 pin=next(x for x in mcu['pins'] if x['net']==nn)
 number=int(pin['name'].replace('GPIO',''))
 assert number==int(re.search(r'constexpr int '+field+r'\s*=\s*(\d+)',header).group(1))
 verified[field]={'gpio':number,'carrier_pin':'U1.'+pin['number'],'net':nn}

# DC and settling analysis: the 30-60k pull values are stress scenarios, not datasheet limits.
import math,itertools
rt,rb=10000,1200
unloaded=[];loaded=[];settled=[]
for supply,top,bottom,cap,pull in itertools.product([3.3*.95,3.3*1.05],[rt*.99,rt*1.01],[rb*.99,rb*1.01],[100e-9*.8,100e-9*1.2],[30000,45000,60000]):
 inf=supply*bottom/(top+bottom);eff=1/(1/bottom+1/pull)
 unloaded.append(inf*1000);loaded.append(supply*eff/(top+eff)*1000)
 tau=1/(1/top+1/bottom)*cap
 settled.append(inf*(1-math.exp(-.010/tau))*1000)
report_values={'top_ohm':rt,'bottom_ohm':rb,'unloaded_mv':[min(unloaded),max(unloaded)],'pulldown_scenario_30k_to_60k_mv':[min(loaded),max(loaded)],'settled_10ms_from_zero_mv':[min(settled),max(settled)]}
assert all(300 < x < 400 for x in report_values['pulldown_scenario_30k_to_60k_mv'])
assert all(300 < x < 400 for x in report_values['settled_10ms_from_zero_mv'])
cpp=(source_root/'lib/GemilaiMateController/src/GemilaiMateController.cpp').read_text().split('void GemilaiMateController::detectBoard()',1)[1].split('void GemilaiMateController::detectAddon()',1)[0]
assert cpp.index('pinMode(DETECT_VALUE_PIN, ANALOG)')<cpp.index('adcAttachPin(DETECT_VALUE_PIN)')<cpp.index('delay(10)')
assert 'INPUT_PULLDOWN' not in cpp
byref={x['ref']:x for x in spec['parts']}
assert byref['R1']['value'].startswith('10k') and byref['R2']['value'].startswith('1.2k')
assert [x['net'] for x in byref['U3']['pins']]==[None,'ZC_SCHMITT_IN','GND','PUMP_ZC','+3V3']
assert not any(x['ref']=='J11' for x in spec['parts'])
assert spec['size_mm']==[90,75]
# Closed-contact LOW with 1k series and 10k || internal pull-up: safely below 0.25 VDD for the stated stress range.
button_ratio=max(1000*1.01/(1000*1.01+1/(1/(10000*.99)+1/pull)) for pull in [30000,45000,60000])
assert button_ratio<.25
report={'schematic_connectivity_matches_design':True,'connected_nets':len(expected),'source_version':spec['source_version'],'firmware_ref':spec['firmware_ref'],'firmware_pin_checks':verified,'gpio35_36_37_unused':True,'divider':report_values,'adc_attached_before_settling':True,'adc_settling_ms':10,'board_id_window_mv':[300,400],'button_closed_low_ratio_vdd_worst_scenario':button_ratio,'zc_interface':'SN74LVC1G17DBV at 3V3, 5.5V-tolerant input; no TXS on ZC','mechanical_reference_size_mm':spec['size_mm'],'mechanical_clone_and_mounts_not_verified':True,'electrical_limits':['30-60kohm internal pulls are scenario values, not guaranteed component limits.','ADC error, GPIO source impedance and physical variation still need bench measurement.','ERC does not model module internals or certify mains isolation.','No physical assembly or USB upload has been performed.']}
(out/'verification.json').write_text(json.dumps(report,indent=2))
print('Connectivity and 13 GPIO checks pass; current divider:',report_values)
