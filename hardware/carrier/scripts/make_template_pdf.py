import json
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape,A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
out=Path(__file__).resolve().parents[1];d=json.loads((out/'design.json').read_text())
pdfmetrics.registerFont(TTFont('Arial',next(str(p) for p in [Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')] if p.exists())))
c=canvas.Canvas(str(out/'mounting-template-1to1.pdf'),pagesize=landscape(A4));c.setTitle('GemilaiMate v0.1: template 1:1 and assembly');c.setAuthor('Rico-X')
def txt(x,y,t,n=9,color='#182838'):
 c.setFillColor(color);c.setFont('Arial',n);c.drawString(x*mm,y*mm,t)
def draw(ox,oy,scale,labels=False):
 def pt(x,y):return((ox+scale*x)*mm,(oy-scale*y)*mm)
 c.setLineWidth(.18*mm);c.setStrokeColorRGB(.1,.15,.2);c.rect(ox*mm,(oy-46*scale)*mm,90*scale*mm,46*scale*mm)
 for x,y in d['mounts_mm']:
  c.circle(*pt(x,y),1.6*scale*mm,stroke=1,fill=0)
  c.line(*pt(x-2,y),*pt(x+2,y));c.line(*pt(x,y-2),*pt(x,y+2))
 for part in d['parts']:
  a,b,e,f=part['rect'];smd=part['ref'].startswith(('R','C')) or part['ref']=='U3'
  c.setStrokeColorRGB(*((.3,.5,.7) if smd else (.6,.65,.7)));c.setLineWidth(.1*mm)
  c.rect((ox+a*scale)*mm,(oy-f*scale)*mm,(e-a)*scale*mm,(f-b)*scale*mm)
  for pin in part.get('physical_pads',part['pins']):
   x,y=pin['x'],pin['y'];c.setStrokeColorRGB(.15,.2,.25)
   if smd:
    hx,hy=(.28,.5) if part['ref']=='U3' else (.5,.725)
    c.rect((ox+(x-hx)*scale)*mm,(oy-(y+hy)*scale)*mm,hx*2*scale*mm,hy*2*scale*mm)
   else:c.circle(*pt(x,y),.5*scale*mm,stroke=1,fill=0)
   if pin['number']=='1':
    c.setFillColorRGB(.7,.1,.1);c.circle(*pt(x,y),.16*scale*mm,stroke=0,fill=1)
  if labels:
   xx=(a+e)/2;yy=b-.7
   if part['ref']=='U1':xx=25;yy=20
   if part['ref']=='U2':xx=82.5;yy=18
   if part['ref'] in ['C3','R11']:yy=11.9
   if part['ref']=='R10':xx=70.5;yy=2
   txt(ox+scale*xx-2,oy-scale*yy,part['ref'],7)
 a,b,e,f=d['rf_keepout'];c.setStrokeColorRGB(.1,.5,.5);c.setDash(1.5*mm,1*mm)
 c.rect((ox+a*scale)*mm,(oy-f*scale)*mm,(e-a)*scale*mm,(f-b)*scale*mm);c.setDash()
 txt(ox+(a+1)*scale,oy-(f-2)*scale,'RF KEEP-OUT',6 if scale==1 else 9,'#226666')
txt(15,194,'GemilaiMate carrier v0.1 - шаблон 1:1',16)
txt(15,184,'Печатать 100%, без вписывания в страницу. Контур PCB 90 x 46 мм.',10)
draw(15,165,1)
txt(15,110,'USB / BOOT / RESET слева; антенна справа.',9)
txt(15,102,'U1: установить только один нижний ряд A или B.',9)
txt(15,94,'Межрядье A 22,86 мм; B 25,40 мм. Шаг 2,54 мм.',9)
txt(15,84,'Контрольная линия: ровно 100 мм',9)
c.setStrokeColorRGB(.1,.15,.2);c.line(15*mm,77*mm,115*mm,77*mm)
for x in [15,115]:c.line(x*mm,75*mm,x*mm,79*mm)
txt(15,64,'Сначала приложить реальный DevKit и гнёзда к шаблону.',9)
txt(15,55,'Нижние детали DevKit должны быть минимум в 5 мм от carrier.',9)
txt(15,46,'Часть SMD находится под поднятой платой DevKit.',9)
txt(15,37,'2 отверстия Ø3,2 мм: (3;3), (87;43) от верхнего левого угла.',9)
txt(15,28,'Крепёж и место в Gemilai ещё не проверены.',9,'#953a23')
txt(132,166,'Перед изготовлением / сборкой',12)
rows=[
 'Сверить 44 контакта и GPIO38/48 своего ESP32-S3 N8R8.',
 'Проект: github.com/Rico-X/GemilaiMate',
 'Высота, жгуты, внешние модули и место в Gemilai не измерены.',
 '',
 '20 SMD сверху: R1-R13, C1-C6, U3 SOT-23-5.',
 'U2 SN74AHCT125N DIP14, выводные разъёмы P2,54.',
 'JP1 снять при USB; JP3 1-2 = VIN 5 В, 2-3 = 3,3 В.',
 'R13 = 0 Ом, разрыв выхода буфера SSR для переделки.',
 '',
 'J8 - только сухие контакты на GND.',
 'J9 - питание USB дисплея, не PA/Grove.',
 'J10 нагревателя в этой адаптации не подключать.',
 'Сетевых цепей на carrier нет. Источник стенда 5 В изолированный.',
 '',
 'На следующей странице - увеличенная монтажная схема.',
 'Красная точка обозначает контакт 1. Круги показывают отверстия.',
 'Точные Gerber/посадочные места находятся в KiCad-проекте.'
]
for i,t in enumerate(rows):txt(132,155-i*7,t,8.2)
txt(15,13,'28.10.2026 | Предварительный прототип | Физическая сборка и USB-запись не выполнялись | 1 / 2',8)
c.showPage()
txt(15,195,'Монтаж сверху - v0.1',16)
txt(15,185,'Увеличено 2,7:1. Сначала SMD, затем U2/разъёмы, затем гнёзда U1 и проверка.',10)
draw(20,171,2.7,True)
txt(20,37,'R1/R3/R4/R5/R8/R9/R11: 10 кОм; R2: 1,2 кОм; R6/R7/R10/R12: 1 кОм; R13: 0 Ом. Все 0805.',9)
txt(20,29,'C1-C6: 100 нФ X7R 50 В 0805. U3: SN74LVC1G17DBVR; pin 1 NC, 2 A, 3 GND, 4 Y, 5 VCC.',9)
txt(20,21,'Увеличенный рисунок не подтверждает совпадение посадочных мест с клонами. Сверить оригинал и даташиты.',8,'#953a23')
txt(20,12,'28.10.2026 | 2 / 2 | Координаты для автомата: manufacturing/CPL-SMD.csv; ориентацию U3 проверить по pin 1.',8)
c.showPage();c.save();print(out/'mounting-template-1to1.pdf')
