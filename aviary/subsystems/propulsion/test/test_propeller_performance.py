import unittest

import numpy as np
import openmdao.api as om

from openmdao.utils.assert_utils import assert_check_partials, assert_near_equal
from dymos.models.atmosphere import USatm1976Comp

from aviary.constants import TSLS_DEGR
from aviary.variable_info.variables import Aircraft
from aviary.subsystems.propulsion.propeller_performance import PropellerPerformance
from aviary.variable_info.variables import Aircraft, Dynamic
from aviary.variable_info.options import get_option_defaults

# Setting up truth values from GASP
CT = np.array([0.27651, 0.20518, 0.13093, 0.10236, 0.10236, 0.19331,
               0.10189, 0.10189, 0.18123, 0.08523, 0.06463, 0.02800])
XFT = np.array([1.0, 1.0, 0.9976, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
CTX = np.array([0.27651, 0.20518, 0.13062, 0.10236, 0.10236, 0.19331,
               0.10189, 0.10189, 0.18123, 0.08523, 0.06463, 0.02800])
three_quart_blade_angle = np.array(
    [25.17, 29.67, 44.23, 31.94, 31.94, 17.44, 33.43, 33.43, 20.08, 30.28, 29.50, 28.10])
thrust = np.array([4634.8, 3415.9, 841.5, 1474.3, 1400.6, 3923.5,
                   1467.6, 1394.2, 3678.3, 1210.4, 917.8, 397.7])
prop_eff = np.array([0.00078, 0.72352, 0.89202, 0.90586, 0.90586, 0.50750,
                     0.90172, 0.90172, 0.47579, 0.83809, 0.76259, 0.49565])
install_loss = np.array([0.0133, 0.02, 0.034, 0.0, 0.05, 0.05,
                         0.0, 0.05, 0.05, 0.0140, 0.0140, 0.0140])
install_eff = np.array([0.00077, 0.70904, 0.86171, 0.90586, 0.86056, 0.48213,
                        0.90172, 0.85664, 0.45200, 0.82635, 0.75190, 0.48871])


class PropellerPerformanceTest(unittest.TestCase):
    def setUp(self):
        options = get_option_defaults()
        options.set_val(Aircraft.Design.COMPUTE_INSTALLATION_LOSS,
                        val=True, units='unitless')
        options.set_val(Aircraft.Engine.NUM_PROPELLER_BLADES,
                        val=4, units='unitless')
        options.set_val(Aircraft.Engine.GENERATE_FLIGHT_IDLE, False)

        prob = om.Problem()

        num_nodes = 3
        prob.model.add_subsystem(
            name='atmosphere',
            subsys=USatm1976Comp(num_nodes=num_nodes),
            promotes_inputs=[('h', Dynamic.Mission.ALTITUDE)],
            promotes_outputs=[
                ('sos', Dynamic.Mission.SPEED_OF_SOUND), ('rho', Dynamic.Mission.DENSITY),
                ('temp', Dynamic.Mission.TEMPERATURE), ('pres', Dynamic.Mission.STATIC_PRESSURE)],
        )

        prob.model.add_subsystem(
            'compute_mach',
            om.ExecComp(f'{Dynamic.Mission.MACH} = 0.00150933 * {Dynamic.Mission.VELOCITY} * ({TSLS_DEGR} / {Dynamic.Mission.TEMPERATURE})**0.5',
                        mach={'units': 'unitless', 'val': np.zeros(num_nodes)},
                        velocity={'units': 'knot', 'val': np.zeros(num_nodes)},
                        temperature={'units': 'degR', 'val': np.zeros(num_nodes)},
                        has_diag_partials=True,
                        ),
            promotes=['*'],
        )

        pp = prob.model.add_subsystem(
            'pp',
            PropellerPerformance(num_nodes=num_nodes, aviary_options=options),
            promotes_inputs=['*'],
            promotes_outputs=["*"],
        )

        pp.set_input_defaults(Aircraft.Engine.PROPELLER_DIAMETER, 10, units="ft")
        pp.set_input_defaults(Dynamic.Mission.TEMPERATURE, 650. *
                              np.ones(num_nodes), units="degR")
        pp.set_input_defaults(Dynamic.Mission.PROPELLER_TIP_SPEED,
                              800 * np.ones(num_nodes), units="ft/s")
        pp.set_input_defaults(Dynamic.Mission.VELOCITY,
                              100. * np.ones(num_nodes), units="knot")
        num_blades = 4
        options.set_val(Aircraft.Engine.NUM_PROPELLER_BLADES,
                        val=num_blades, units='unitless')
        options.set_val(Aircraft.Design.COMPUTE_INSTALLATION_LOSS,
                        val=True, units='unitless')
        prob.setup()

        prob.set_val(Aircraft.Engine.PROPELLER_DIAMETER, 10.5, units="ft")
        prob.set_val(Aircraft.Engine.PROPELLER_ACTIVITY_FACTOR, 114.0, units="unitless")
        prob.set_val(Aircraft.Engine.PROPELLER_INTEGRATED_LIFT_COEFFICIENT,
                     0.5, units="unitless")
        prob.set_val(Aircraft.Nacelle.AVG_DIAMETER, 2.8875, units='ft')

        self.prob = prob
        self.options = options

    def compare_results(self, case_idx_begin, case_idx_end):
        p = self.prob
        cthr = p.get_val('thrust_coefficient')
        ctlf = p.get_val('comp_tip_loss_factor')
        tccl = p.get_val('thrust_coefficient_comp_loss')
        angb = p.get_val('blade_angle')
        thrt = p.get_val('propeller_thrust')
        peff = p.get_val('propeller_efficiency')
        lfac = p.get_val(Dynamic.Mission.INSTALLATION_LOSS_FACTOR)
        ieff = p.get_val('install_efficiency')

        tol = 0.005

        for case_idx in range(case_idx_begin, case_idx_end):
            idx = case_idx - case_idx_begin
            assert_near_equal(cthr[idx], CT[case_idx], tolerance=tol)
            assert_near_equal(ctlf[idx], XFT[case_idx], tolerance=tol)
            assert_near_equal(tccl[idx], CTX[case_idx], tolerance=tol)
            assert_near_equal(
                angb[idx], three_quart_blade_angle[case_idx], tolerance=tol)
            assert_near_equal(thrt[idx], thrust[case_idx], tolerance=tol)
            assert_near_equal(peff[idx], prop_eff[case_idx], tolerance=tol)
            assert_near_equal(lfac[idx], install_loss[case_idx], tolerance=tol)
            assert_near_equal(ieff[idx], install_eff[case_idx], tolerance=tol)

    def test_case_0_1_2(self):
        # Case 0, 1, 2, to test installation loss factor computation.
        prob = self.prob
        prob.set_val(Dynamic.Mission.ALTITUDE, [0.0, 0.0, 25000.0], units="ft")
        prob.set_val(Dynamic.Mission.VELOCITY, [0.10, 125.0, 300.0], units="knot")
        prob.set_val(Dynamic.Mission.PROPELLER_TIP_SPEED,
                     [800.0, 800.0, 750.0], units="ft/s")
        prob.set_val(Dynamic.Mission.SHAFT_POWER, [1850.0, 1850.0, 900.0], units="hp")
        prob.set_val(Dynamic.Mission.PERCENT_ROTOR_RPM_CORRECTED,
                     [1.0], units="unitless")
        prob.set_val(Aircraft.Design.MAX_PROPELLER_TIP_SPEED,
                     [800.00, 800.0, 750.0], units="ft/s")

        prob.run_model()
        self.compare_results(case_idx_begin=0, case_idx_end=2)

        partial_data = prob.check_partials(
            out_stream=None, compact_print=True, show_only_incorrect=True, form='central', method="fd",
            minimum_step=1e-12, abs_err_tol=5.0E-4, rel_err_tol=5.0E-5, excludes=["*atmosphere*"])
        assert_check_partials(partial_data, atol=5e-4, rtol=1e-4)

    def test_case_3_4_5(self):
        # Case 3, 4, 5, to test normal cases.
        prob = self.prob
        options = self.options

        options.set_val(Aircraft.Design.COMPUTE_INSTALLATION_LOSS,
                        val=False, units='unitless')
        prob.setup()
        prob.set_val(Dynamic.Mission.INSTALLATION_LOSS_FACTOR,
                     [0.0, 0.05, 0.05], units="unitless")
        prob.set_val(Aircraft.Engine.PROPELLER_DIAMETER, 12.0, units="ft")
        prob.set_val(Aircraft.Engine.PROPELLER_ACTIVITY_FACTOR, 150.0, units="unitless")
        prob.set_val(Aircraft.Engine.PROPELLER_INTEGRATED_LIFT_COEFFICIENT,
                     0.5, units="unitless")
        prob.set_val(Dynamic.Mission.ALTITUDE, [10000.0, 10000.0, 0.0], units="ft")
        prob.set_val(Dynamic.Mission.VELOCITY, [200.0, 200.0, 50.0], units="knot")
        prob.set_val(Dynamic.Mission.PROPELLER_TIP_SPEED,
                     [750.0, 750.0, 785.0], units="ft/s")
        prob.set_val(Dynamic.Mission.SHAFT_POWER, [1000.0, 1000.0, 1250.0], units="hp")
        prob.set_val(Dynamic.Mission.PERCENT_ROTOR_RPM_CORRECTED,
                     [1.0], units="unitless")
        prob.set_val(Aircraft.Design.MAX_PROPELLER_TIP_SPEED,
                     [769.70, 769.70, 769.70], units="ft/s")

        prob.run_model()
        self.compare_results(case_idx_begin=3, case_idx_end=5)

        partial_data = prob.check_partials(
            out_stream=None, compact_print=True, show_only_incorrect=True, form='central', method="fd",
            minimum_step=1e-12, abs_err_tol=5.0E-4, rel_err_tol=5.0E-5, excludes=["*atmosphere*"])
        assert_check_partials(partial_data, atol=1.5e-4, rtol=1e-4)

    def test_case_6_7_8(self):
        # Case 6, 7, 8, to test odd number of blades.
        prob = self.prob
        options = self.options

        num_blades = 3
        options.set_val(Aircraft.Engine.NUM_PROPELLER_BLADES,
                        val=num_blades, units='unitless')
        options.set_val(Aircraft.Design.COMPUTE_INSTALLATION_LOSS,
                        val=False, units='unitless')
        prob.setup()
        prob.set_val(Dynamic.Mission.INSTALLATION_LOSS_FACTOR,
                     [0.0, 0.05, 0.05], units="unitless")
        prob.set_val(Aircraft.Engine.PROPELLER_DIAMETER, 12.0, units="ft")
        prob.set_val(Aircraft.Engine.PROPELLER_ACTIVITY_FACTOR, 150.0, units="unitless")
        prob.set_val(Aircraft.Engine.PROPELLER_INTEGRATED_LIFT_COEFFICIENT,
                     0.5, units="unitless")
        prob.set_val(Dynamic.Mission.ALTITUDE, [10000.0, 10000.0, 0.0], units="ft")
        prob.set_val(Dynamic.Mission.VELOCITY, [200.0, 200.0, 50.0], units="knot")
        prob.set_val(Dynamic.Mission.PROPELLER_TIP_SPEED,
                     [750.0, 750.0, 785.0], units="ft/s")
        prob.set_val(Dynamic.Mission.SHAFT_POWER, [1000.0, 1000.0, 1250.0], units="hp")
        prob.set_val(Dynamic.Mission.PERCENT_ROTOR_RPM_CORRECTED,
                     [1.0], units="unitless")
        prob.set_val(Aircraft.Design.MAX_PROPELLER_TIP_SPEED,
                     [769.70, 769.70, 769.70], units="ft/s")

        prob.run_model()
        self.compare_results(case_idx_begin=6, case_idx_end=8)

        partial_data = prob.check_partials(
            out_stream=None, compact_print=True, show_only_incorrect=True, form='central', method="fd",
            minimum_step=1e-12, abs_err_tol=5.0E-4, rel_err_tol=5.0E-5, excludes=["*atmosphere*"])
        assert_check_partials(partial_data, atol=1e-4, rtol=1e-4)

    def test_case_9_10_11(self):
        # Case 9, 10, 11, to test CLI > 0.5
        prob = self.prob
        prob.set_val(Aircraft.Engine.PROPELLER_DIAMETER, 12.0, units="ft")
        prob.set_val(Aircraft.Nacelle.AVG_DIAMETER, 2.4, units='ft')
        prob.set_val(Aircraft.Engine.PROPELLER_ACTIVITY_FACTOR, 150.0, units="unitless")
        prob.set_val(Aircraft.Engine.PROPELLER_INTEGRATED_LIFT_COEFFICIENT,
                     0.65, units="unitless")
        prob.set_val(Dynamic.Mission.ALTITUDE, [10000.0, 10000.0, 10000.0], units="ft")
        prob.set_val(Dynamic.Mission.VELOCITY, [200.0, 200.0, 200.0], units="knot")
        prob.set_val(Dynamic.Mission.PROPELLER_TIP_SPEED,
                     [750.0, 750.0, 750.0], units="ft/s")
        prob.set_val(Dynamic.Mission.SHAFT_POWER, [900.0, 750.0, 500.0], units="hp")
        prob.set_val(Dynamic.Mission.PERCENT_ROTOR_RPM_CORRECTED,
                     [1.0], units="unitless")
        prob.set_val(Aircraft.Design.MAX_PROPELLER_TIP_SPEED,
                     [769.70, 769.70, 769.70], units="ft/s")

        prob.run_model()
        self.compare_results(case_idx_begin=9, case_idx_end=11)

        partial_data = prob.check_partials(
            out_stream=None, compact_print=True, show_only_incorrect=True, form='central', method="fd",
            minimum_step=1e-12, abs_err_tol=5.0E-4, rel_err_tol=5.0E-5, excludes=["*atmosphere*"])
        # remove partial derivative of 'comp_tip_loss_factor' with respect to
        # 'aircraft:engine:propeller_integrated_lift_coefficient' from assert_check_partials
        partial_data_hs = partial_data['pp.hamilton_standard']
        key_pair = ('comp_tip_loss_factor',
                    'aircraft:engine:propeller_integrated_lift_coefficient')
        del partial_data_hs[key_pair]
        assert_check_partials(partial_data, atol=1.5e-3, rtol=1e-4)


if __name__ == "__main__":
    unittest.main()
