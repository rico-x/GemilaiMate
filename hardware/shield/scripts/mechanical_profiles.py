"""Explicit prototype allowances, never substituted for measured geometry."""


def build_profiles(design):
    parts = {c['ref']: c for c in design['parts']}
    occupied = []
    for ref, height in [('U1', 22), ('J2', 16), ('J7', 16), ('J3', 24)]:
        a, b, c, d = parts[ref]['rect']
        occupied.append(dict(id=ref+'-module', owner=ref, kind='module',
                             bbox_mm=[a,b,8.5,c,d,height], measured=False))
    for ref in ['J1', 'J4', 'J8', 'J9', 'J5', 'J6']:
        a, b, c, d = parts[ref]['rect']
        low = 8.5 if ref in ['J5', 'J6'] else 2.54
        box = [round(a-.5,5),round(b-.5,5),low,
               round(c+.5,5),round(d+.5,5),low+11]
        occupied.append(dict(id=ref+'-mated-plug', owner=ref, kind='mated_plug',
                             bbox_mm=box, measured=False))
        # Reserve the first section of cable outside the PCB. The route
        # further into the machine and external power modules is unplaced.
        if ref in ['J1', 'J9']:
            exit_box=[box[0],-15,low,box[3],box[1],low+15]
        elif ref=='J6':
            exit_box=[box[3],box[1],low,105,box[4],low+15]
        else:
            exit_box=[box[0],box[4],low,box[3],90,low+15]
        occupied.append(dict(id=ref+'-cable-exit', owner=ref, kind='cable_exit',
                             bbox_mm=exit_box, measured=False))
    a,b,c,d=parts['J3']['rect']
    occupied.append(dict(id='J3-thermocouple-exit',owner='J3',kind='cable_exit',
                         bbox_mm=[a,d,11.04,c,90,26],measured=False))
    return dict(status='DESIGN ALLOWANCES ONLY - real plugs/modules unmeasured',
                coordinates='mm from PCB top-left; z above PCB top',
                occupied=occupied,
                fasteners=dict(head_diameter_max_mm=5.5,washer_allowed=False,
                               minimum_planar_gap_mm=1.0),
                external_power_modules=[
                    dict(reference='J5',mounting_mode='external_wired',
                         seller_pcb_outline_mm=[60,42],actual_height_mm=None,
                         reserved_size_mm=[80,65,65],reservation_is_measured=False,
                         placement_mm=None,clearance_result='NOT ASSESSED - external layout required'),
                    dict(reference='J6',mounting_mode='external_wired',
                         seller_pcb_outline_mm=None,actual_height_mm=None,
                         reserved_size_mm=[60,45,40],reservation_is_measured=False,
                         placement_mm=None,clearance_result='NOT ASSESSED - external layout required')])
