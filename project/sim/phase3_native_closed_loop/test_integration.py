import time
import unittest
from dataclasses import replace
import bootstrap
import planner_p2p_reference as pr
import s4_task_reference as m
import phase3_link_protocol as lp
from s4_port import ModelS4Port
from ps_path_service import PathServiceCore, ServiceConfig, LinkState
from sim_config import load
from run_closed_loop import plan_for
from simulator_service import SimulatorPathService
from orchestrator import ServiceEventTap


class IntegrationTests(unittest.TestCase):
    def setup_service(self, virtual=False):
        data,cfg,tables = load(bootstrap.HERE/"examples/SIMULATION_CONFIG.json")
        cfg = replace(cfg, mode_b=True, hold_policy=True, tray_exit=True)
        plant = m.Plant(s1_mode=m.S1_MODE_LINE,home=tables.keypoints[0],
                        validate_fn=m.planner_validate_fn(pr))
        model = m.S4TaskModel(cfg,tables,plant)
        port = ModelS4Port(model)
        port.command(m.Cmd.ENABLE)
        model.vision(True,m.BACKGROUND,True); port.advance(1)
        model.vision(True,1,True); port.advance(1)
        paths = {int(k):[m.Segment(tuple(s["target"]),s["n"],s["na"],s["profile"],s["flags"])
                        for s in v] for k,v in data["paths"].items()}
        plan,limits = plan_for(1,1,paths,cfg,tables)
        config = ServiceConfig(tables.keypoints[0],tables.keypoints[1],limits,10000)
        kwargs = dict(simulation_only=True,fixture=True,confirm_no_robot=True) if virtual else {}
        service = (SimulatorPathService if virtual else PathServiceCore)(port,config,pr,**kwargs)
        service.link = LinkState.SESSION
        service._last_rx = service._last_hb_tx = time.monotonic()
        service.step()
        return service,plan,model

    def test_original_line_gate_still_blocks_synthetic_bench(self):
        service,plan,model = self.setup_service()
        output = service._on_submit(lp.encode_plan(plan))
        self.assertEqual(output[0][1][1],lp.PathResult.NOT_EXECUTABLE)
        self.assertEqual(model.state,m.State.WAIT_PATH)

    def test_simulator_admission_commits_once_preserves_line(self):
        service,plan,model = self.setup_service(True)
        output = service._on_submit(lp.encode_plan(plan))
        self.assertEqual(output[0][1][1],lp.PathResult.COMMITTED)
        self.assertEqual(service.port.status().s1_mode,m.S1_MODE_LINE)
        duplicate = service._on_submit(lp.encode_plan(plan))
        self.assertEqual(duplicate[0][1][1],lp.PathResult.DUPLICATE)

    def test_simulator_admission_requires_explicit_destination(self):
        service,plan,model = self.setup_service()
        with self.assertRaises(ValueError):
            SimulatorPathService(service.port,service.cfg,pr,simulation_only=True,fixture=True)

    def test_event_arriving_between_polls_is_retained_for_service(self):
        class Port:
            events = []
            def drain_events(self):
                events,self.events = self.events,[]
                return events
        port = Port()
        tap = ServiceEventTap(port)
        self.assertEqual(tap.drain_events(),[])
        port.events = [m.Event.SELECTED]
        self.assertEqual(tap.take(),[])
        self.assertEqual(port.events,[m.Event.SELECTED])
        self.assertEqual(tap.drain_events(),[m.Event.SELECTED])
        self.assertEqual(tap.take(),[m.Event.SELECTED])
        self.assertEqual(tap.take(),[])


if __name__ == "__main__":
    unittest.main()
