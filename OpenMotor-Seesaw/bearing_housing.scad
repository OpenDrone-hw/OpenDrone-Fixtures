// Printed 608ZZ housing, alternative to the press-fit ply seat.
// Use with: python3 generate.py --bearing printed  (upright gets a 12 mm hole
// and four M3 holes on a 16 mm radius at 45 degrees). The housing sits on the
// OUTER face of the upright, bearing inserted from the outside, M3 x 20 screws
// and nuts on the inner face. Rod length grows by 2 x housing thickness
// (use M8 x 100). Not printed or tested.
bearing_od = 22.0;
bearing_w  = 7.0;
fit        = 0.10;     // printer clearance on the seat diameter
lip        = 1.5;      // back wall that stops the bearing
flange_d   = 44.0;     // matches the upright boss
m3_r       = 16.0;
$fn = 96;

difference() {
    cylinder(d = flange_d, h = lip + bearing_w);
    translate([0, 0, lip]) cylinder(d = bearing_od + fit, h = bearing_w + 1);
    translate([0, 0, -1]) cylinder(d = 16, h = lip + 2);          // clear of the inner race
    for (a = [45, 135, 225, 315])
        translate([m3_r * cos(a), m3_r * sin(a), -1]) cylinder(d = 3.4, h = lip + bearing_w + 2);
}
