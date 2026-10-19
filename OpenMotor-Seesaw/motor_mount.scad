// Printed motor mount for the OpenMotor 2306 on the seesaw arm.
// A saddle: two side plates clamp the 8 mm ply arm (M3 screws through the arm's
// 10 mm grid, 12 holes, nuts on the far side); a platform floats MOUNT_GAP above
// the arm top and carries the motor. Motor screws come up from below through four
// slotted holes that cover both the 16 x 16 and the 19 x 19 mm M3 pattern.
// Centre hole: shaft and circlip clearance. The wire slot runs toward the arm.
// All numbers come from motor_mount_params.scad (written by generate.py).
// Print: platform up is fine, no supports needed except under the platform
// overhang beyond the side plates (or print on its back, side plate down).
// Not printed or test-fitted yet.
include <motor_mount_params.scad>;
$fn = 64;

module mount() {
    top = GAP + PLAT_T;
    difference() {
        union() {
            // platform
            translate([-SIDE_HALF, -PLAT_W / 2, GAP]) cube([PLAT_X1 + SIDE_HALF, PLAT_W, PLAT_T]);
            // side plates, either side of the arm
            for (s = [-1, 1])
                translate([-SIDE_HALF, s > 0 ? ARM_T / 2 + CLR : -(ARM_T / 2 + CLR + WALL), SIDE_Z0])
                    cube([2 * SIDE_HALF, WALL, top - SIDE_Z0]);
        }
        // grid holes through both side plates (arm centre is at z = -ARM_H / 2)
        for (c = [0 : GRID_COLS - 1], r = [0 : GRID_ROWS - 1])
            translate([(c - (GRID_COLS - 1) / 2) * GRID_PITCH, 0,
                       -ARM_H / 2 + (r - (GRID_ROWS - 1) / 2) * GRID_PITCH])
                rotate([90, 0, 0]) cylinder(d = HOLE_D, h = 3 * ARM_T, center = true);
        // motor: centre hole, wire slot, four slotted holes (16 and 19 mm patterns)
        translate([MOTOR_X, 0, 0]) {
            cylinder(d = CENTER_D, h = 3 * top, center = true);
            translate([-18, -4, -top]) cube([18, 8, 3 * top]);
            for (a = [45, 135, 225, 315])
                hull() for (p = [PATTERN_A, PATTERN_B])
                    translate([p * sqrt(2) / 2 * cos(a), p * sqrt(2) / 2 * sin(a), -top])
                        cylinder(d = HOLE_D, h = 3 * top);
        }
    }
}

mount();
