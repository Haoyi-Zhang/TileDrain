import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from contracts import Instance,closure,synthesize,verify
from general import analyze,verify_analysis
from mutations import run_controls
from inputs import instance_from_dict,instance_dict
from semantics import capability,adapter_alu,reference_alu,OPS

class ContractTests(unittest.TestCase):
    def test_declared_negative_controls(self):
        self.assertEqual(len(run_controls()),31)
    def test_empty_epoch(self):
        x=Instance((),(),(),(),(0,),0)
        a=analyze(x);self.assertTrue(verify_analysis(x,a));self.assertEqual(a['cut']['drain'],[])
    def test_aligned_fast_path(self):
        q=closure(4,[(0,1),(2,3)])
        x=Instance((0,0,0,0),q,(0,0,1,1),(1,2,2,1),(2,1),0)
        a=synthesize(x);self.assertEqual(a['drain'],[0,2]);self.assertTrue(verify(x,a))
        self.assertEqual(analyze(x)['cut']['drain'],a['drain'])
    def test_capacity_nonmonotone_leastness(self):
        actual=[]
        for cap in range(4):
            x=Instance((0,0,0),(0,0,0),(0,0,0),(1,1,1),(cap,),0)
            a=analyze(x);self.assertTrue(verify_analysis(x,a));actual.append(a['kind'])
        self.assertEqual(actual,['least','no_least','no_least','least'])
    def test_json_roundtrip(self):
        x=Instance((0,),(0,),(0,),(1,),(0,),1)
        self.assertEqual(instance_from_dict(instance_dict(x)),x)
    def test_tiny_alu(self):
        for w in range(1,4):
          for mode in ('native','wide','split'):
            cap=capability(mode,w)
            for a in range(1<<w):
              for b in range(1<<w):
                for c in (0,1):
                  for op in OPS:self.assertEqual(adapter_alu(op,a,b,c,cap),reference_alu(op,a,b,c,w))


class RobustnessTests(unittest.TestCase):
    def test_mandatory_removal_can_restore_alignment(self):
        from robust import effectively_aligned,synthesize_effective,obstruction_capacity
        x=Instance((0,0),(0,0),(0,0),(1,1),(1,),1)
        self.assertTrue(effectively_aligned(x))
        self.assertEqual(synthesize_effective(x)['drain'],[0])
        self.assertIsNone(obstruction_capacity(x))
        self.assertTrue(verify(x,synthesize_effective(x)))
    def test_serial_prefix_then_fork(self):
        from robust import obstruction_capacity
        q=closure(3,[(0,1),(0,2)])
        x=Instance((0,0,0),q,(0,0,0),(2,3,4),(9,),0)
        cap=obstruction_capacity(x)
        self.assertEqual(cap,(4,))
        y=Instance(x.p,x.q,x.lane,x.weight,cap,0)
        a=analyze(y);self.assertEqual(a['kind'],'no_least');self.assertTrue(verify_analysis(y,a))
    def test_encoder_boundary_is_not_unbounded_theorem(self):
        from contracts import MAX_INTEGER
        from robust import effectively_aligned,obstruction_capacity
        m=MAX_INTEGER;q=closure(3,[(0,2),(1,2)])
        x=Instance((0,0,0),q,(0,0,0),(m,m,m),(m,),0)
        self.assertFalse(effectively_aligned(x))
        a=analyze(x);self.assertEqual(a['cut']['drain'],[0,1]);self.assertTrue(verify_analysis(x,a))
        with self.assertRaises(ValueError):obstruction_capacity(x)
    def test_weighted_obstruction_with_cross_lane_source_order(self):
        from robust import obstruction_capacity
        q=closure(4,[(0,2),(1,3),(2,3)])
        x=Instance((0,0,0,0),q,(0,0,1,1),(2,3,1,4),(5,5),0)
        cap=obstruction_capacity(x);self.assertIsNotNone(cap)
        y=Instance(x.p,x.q,x.lane,x.weight,cap,0)
        a=analyze(y);self.assertEqual(a['kind'],'no_least');self.assertTrue(verify_analysis(y,a))

if __name__=='__main__':unittest.main()
