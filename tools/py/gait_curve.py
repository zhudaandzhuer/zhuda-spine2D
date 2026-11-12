#!/usr/bin/env python3
"""Generate continuous contact/swing targets, not a finished character animation."""
import argparse
import csv
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def target(phase, span, lift, contact):
    p = phase % 1.0
    if p < contact:
        return -span + 2 * span * p / contact, 0.0, True
    u = (p - contact) / (1 - contact)
    tangent = 2 * span * (1 - contact) / contact
    x = (2*u**3 - 3*u*u + 1)*span + (u**3 - 2*u*u + u)*tangent + (-2*u**3 + 3*u*u)*(-span) + (u**3-u*u)*tangent
    return x, lift*16*u*u*(1-u)**2, False


def self_test():
    for contact in (0.4, 0.6):
        for span in (1, 29):
            h = 1e-7
            for seam in (contact, 1.0):
                left = target(seam-h, span, 26, contact)
                center = target(seam, span, 26, contact)
                right = target(seam+h, span, 26, contact)
                assert abs(left[0]-right[0]) < 1e-4
                vl = (center[0]-left[0])/h
                vr = (right[0]-center[0])/h
                assert math.isclose(vl, vr, rel_tol=1e-4, abs_tol=1e-3)
                assert abs(center[1]) < 1e-9
    print('PASS: contact/swing position and velocity continuity; loop endpoint')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--span', type=float, default=29)
    p.add_argument('--lift', type=float, default=26)
    p.add_argument('--contact', type=float, default=.6)
    p.add_argument('--duration', type=float, default=1.2)
    p.add_argument('--samples', type=int, default=121)
    p.add_argument('--out', type=Path)
    p.add_argument('--self-test', action='store_true')
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    if not (a.span > 0 and a.lift >= 0 and 0 < a.contact < 1 and a.duration > 0 and a.samples >= 3 and a.out):
        p.error('Provide --out; span/duration > 0, lift >= 0, contact in (0,1), samples >= 3')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['time', 'near_x', 'near_y', 'near_contact', 'far_x', 'far_y', 'far_contact'])
        for i in range(a.samples):
            phase = i/(a.samples-1)
            near, far = target(phase, a.span, a.lift, a.contact), target(phase+.5, a.span, a.lift, a.contact)
            writer.writerow([phase*a.duration, *near, *far])
    print(f'Wrote {a.samples} targets to {a.out}; adapt direction, root velocity, and rig coordinates.')


if __name__ == '__main__':
    main()
