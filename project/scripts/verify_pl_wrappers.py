"""Structural composition proof: inline wrappers and compare normalized ASTs.

All wrapper ports/parameters must be identity bindings. Only original instance
statements and uninitialized wire declarations are allowed inside wrappers.
The checker compares every parent declaration, assignment, procedural block,
generate condition and instance after inlining. It never simulates hardware.
"""
from pathlib import Path
import hashlib
import json
from pyslang.syntax import SyntaxTree
from refactor_pl_wrappers import module,plain,nodes,parameters
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'board_evidence/pl_wrappers_v1'


def main():
    manifest=json.loads((OUT/'manifest.json').read_bytes());definitions={};trees=[]
    source=ROOT/manifest.get('proof_source_root','.')
    for w in manifest['wrappers']:
        p=source/w['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==w['sha256']
        t=SyntaxTree.fromFile(str(p));trees.append(t);assert len(t.diagnostics)==0
        m=module(t)[0];body=plain(m)['members']
        assert all(x['kind'] in ('NetDeclaration','HierarchyInstantiation') for x in body)
        assert [x for x in body if x['kind']=='HierarchyInstantiation']==w['original_instances'],w['module']
        definitions[w['module']]=(w,body)
    def norm(x):
        if isinstance(x,list):
            result=[]
            for item in x:
                item=norm(item);result.extend(item if isinstance(item,list) else [item])
            return result
        if not isinstance(x,dict):return x
        if x.get('kind')=='HierarchyInstantiation' and x['type']['text'] in definitions:
            w,body=definitions[x['type']['text']];instances=x['instances'];assert len(instances)==1
            bindings=[p for p in instances[0]['connections'] if p['kind']=='NamedPortConnection']
            assert {p['name']['text'] for p in bindings}=={p['name'] for p in w['ports']}
            for p in bindings:
                expression=p['expr']
                while expression['kind'] in ('SimplePropertyExpr','SimpleSequenceExpr'):expression=expression['expr']
                assert expression['kind']=='IdentifierName' and expression['identifier']['text']==p['name']['text']
            supplied=[p for p in x.get('parameters',{}).get('parameters',[]) if p['kind']=='NamedParamAssignment']
            assert {p['name']['text'] for p in supplied}==set(w['parameters'])
            for p in supplied:assert p['expr']['kind']=='IdentifierName' and p['expr']['identifier']['text']==p['name']['text']
            return norm(body)
        if x.get('kind') in ('NetDeclaration','DataDeclaration'):
            result=[]
            for d in x['declarators']:
                if d['kind']!='Declarator':continue
                result.append({**{k:norm(v) for k,v in x.items() if k!='declarators'},'declarators':[norm(d)]})
            return result
        result={k:norm(v) for k,v in x.items()}
        # Module/generate members are concurrent; statement and expression lists
        # remain ordered. Splitting a wire declaration adds no state or drivers.
        if 'members' in result:result['members']=sorted(result['members'],key=lambda v:json.dumps(v,sort_keys=True))
        return result
    parents=[]
    for name,record in manifest['parents'].items():
        p=source/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==record['after_sha256']
        before=OUT/'before'/Path(name).relative_to('native_motion/rtl')
        assert hashlib.sha256(before.read_bytes()).hexdigest()==record['before_sha256']
        a=SyntaxTree.fromFile(str(before));b=SyntaxTree.fromFile(str(p));trees.extend([a,b]);assert len(a.diagnostics)==len(b.diagnostics)==0
        original=norm(plain(module(a)[0]));current=norm(plain(module(b)[0]))
        if original!=current:
            (OUT/'expected_ast.json').write_text(json.dumps(original,indent=2))
            (OUT/'actual_ast.json').write_text(json.dumps(current,indent=2))
            raise ValueError('Expanded structure differs: '+name)
        parents.append(name)
    report=dict(passed=True,method='IDENTITY_PORT_PARAMETER_BINDING_AND_EXPANDED_CONCURRENT_AST_EQUALITY',
        parent_modules=len(parents),structural_wrappers=len(definitions),leaf_instances_moved=sum(len(w['children']) for w in manifest['wrappers']),
        state_or_timing_added=False,new_bit_generated=False,hardware_access=False,
        proof_source_root=manifest.get('proof_source_root','.'),functional_b_changes_excluded=True,
        source_hashes={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in parents+[w['file'] for w in manifest['wrappers']]})
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
