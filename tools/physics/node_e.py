"""Stage 2, node E (spec §5.2): the spring motor and the governor. From node B's integration: the start from the cycle
latch, the free running speed (governor alone: motor.W_FREE), the speed at the end of the revolution and the blow on
the cycle latch when the stop arm meets it (the shaft, its cams and the train behind it stop at once). The inertia of
the parts that turn with the cycle shaft is taken from the meshes (with the governor's through the 32/8 pair) and
compared with motor.py's J0 = 4e-5 kg m2.
Usage: python3 -I tools/physics/node_e.py"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import units as U
import numpy as np
import params as P
import node_b as NB

MASS = {x['name']: x for x in json.load(open(os.path.join(U.GEN, 'mass.json')))['parts']}
PARTS = {p['name']: p for p in json.load(open(os.path.join(U.GEN, 'parts.json')))}


def I_axis(n, axis_pt, d):
    m = MASS[n]; c = np.array(m['c']); I = np.array(m['I'])
    d = np.asarray(d, float); d /= np.linalg.norm(d)
    r = c - np.asarray(axis_pt, float); r_perp = r - (r @ d) * d
    return float(d @ I @ d + m['m'] * (r_perp @ r_perp))


def main():
    res = {}
    import parts as PT
    cyc_axis = np.array([0.0, PT.CYC[0], PT.CYC[1]]) * U.MM
    J_shaft = sum(I_axis(n, cyc_axis, (1, 0, 0)) for n, p in PARTS.items() if n in ('cycle shaft', 'cam lift', 'cam rotate', 'cam detent', 'cam hammer',
                                                                                 'cam ribbon', 'cam read', 'cycle stop arm', 'governor gear', 'bevel cycle 1:1', 'pinion C',
                                                                                 'cam rotate return', 'cam lift return'))
    # the governor turns 32/8 = 4 times faster: its inertia counts 16 times
    gov = [n for n in ('governor fan', 'governor arbor', 'governor pinion', 'governor flywheel', 'governor sliding collar', 'governor fixed collar',
                       'governor weight 1', 'governor weight 2', 'governor weight 3', 'governor leaf spring 1', 'governor leaf spring 2',
                       'governor leaf spring 3') if n in MASS]   # rev. 0.14: + flywheel; stage 2b: + the brake
    ga = np.array(MASS['governor arbor']['c'])
    J_gov = sum(I_axis(n, ga, (1, 0, 0)) for n in gov) * 16      # stage 2b: about the arbor (the brake's weights sit off it)
    MO = NB.motor_module()
    res['J_mesh'] = dict(shaft_and_cams=J_shaft, governor_reflected=J_gov, total=J_shaft + J_gov, motor_J0=MO.J0, old_motor_J0=4.0e-5)
    I_rot, m_lift, ro, lo = NB.chain_masses()
    tau = NB.MJ['tau_C']; cg = getattr(MO, 'C_FAN', (tau - MO.TAU_FRIC) / MO.W_FREE ** 2)    # stage 2b: the fan as built
    rows = []
    for lab, (pos, row) in (('без хода (5, −1)', (5, -1)), ('средняя (4, 5)', (4, 5)), ('дальняя (0, 7)', (0, 7))):
        th, dz = NB.target(pos, row)
        for J0, jl in ((MO.J0, 'motor.py'), (J_shaft + J_gov, 'по сеткам')):
            tr = NB.cycle(tau, cg, th, dz, I_rot, m_lift, J0=J0)
            t, phi, w, wd = tr.T
            k30 = np.searchsorted(phi, 30.0)
            E_stop = 0.5 * J0 * w[-1] ** 2
            # the blow on the latch: the stop arm at r = 8 mm meets the latch; printed contact 0.5..3e6 N/m
            r = 8e-3; m_eq = J0 / r ** 2; v = w[-1] * r
            F = [v * math.sqrt(k * m_eq) for k in (0.5e6, 1.5e6, 3e6)]
            F_pad = v * math.sqrt(0.3e6 * m_eq)          # rev. 0.14: polyurethane pad 2 mm on the latch face (6 x 3 mm)
            rows.append(dict(target=lab, J0=jl, t_cycle=float(t[-1]), t_to_30deg_ms=float(t[k30] * 1e3), w_end=float(w[-1]),
                             w_max=float(w.max()), E_stop_mJ=E_stop * 1e3, F_latch_N=F, sigma_MPa=[f / (3e-3 * 1e-3) / 1e6 for f in F],
                             F_pad_N=F_pad, sigma_pad_MPa=F_pad / 18e-6 / 1e6))
    res['rows'] = rows
    res['free_speed'] = dict(W_FREE=MO.W_FREE, t_rev=2 * math.pi / MO.W_FREE, W_CAP=getattr(MO, 'W_CAP', None))
    json.dump(res, open(os.path.join(U.GEN, 'node_e.json'), 'w'), ensure_ascii=False, indent=1, default=float)
    print(res['J_mesh'])
    for r in rows:
        print(r)


if __name__ == '__main__':
    main()
