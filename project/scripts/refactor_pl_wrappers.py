"""Extract pure structural wrappers with slang; preserve all leaf RTL/state.

Run in the isolated RTL tooling environment. The manifest records exact moved
instance expressions and declaration ownership for the independent checker.
This is not an automatic functional partitioner: groups below are reviewed
clock / datapath / memory / control / protocol boundaries.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pyslang.syntax import SyntaxTree

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'board_evidence/pl_wrappers_v1'
GROUPS={
 'autonomous/gesture_autonomous_top_black.v':[
  ('vision_acquisition_pipeline','u_acquisition',['u_camera_init','u_sccb','u_camera_frontend']),
  ('vision_locator_compute','u_locator_compute',['u_locator_model','u_locator','u_top1']),
  ('vision_roi_memory_pipeline','u_roi_memory',['u_camera_memory','u_same_frame_roi','u_classifier_input']),
  ('vision_classifier_compute','u_classifier_compute',['u_classifier_desc','u_classifier_weights','u_classifier']),
  ('vision_schedule_qualifier','u_pipeline_control',['u_bbox','u_scheduler','u_confirm'])],
 'robot/phase3_s4_task_top.v':[
  ('motion_axil_ownership_fabric','u_ownership_fabric',['u_win_traj','u_win_arm','u_win_plan']),
  ('motion_hand_target_pipeline','u_hand_target',['u_regions','u_target']),
  ('motion_task_control','u_task_control',['u_regs','u_fsm','u_link'])],
 'robot/phase3_s2_motion_top.v':[
  ('motion_actuator_pipeline','u_actuator',['u_mux','u_arm_backend'])],
 'hdmi/mode_a_hdmi_output.v':[
  ('display_scan_pipeline','u_scan',['timing','canvas']),
  ('display_telemetry_bridge','u_telemetry',['loc_units','cls_units','status_cdc']),
  ('hdmi_phy_pipeline','u_phy',['eb','eg','er','serializer'])]
}


def module(tree):
    r=tree.root
    if str(r.kind)=='SyntaxKind.ModuleDeclaration':return [r]
    return [n for n in getattr(r,'members',[]) if str(n.kind)=='SyntaxKind.ModuleDeclaration']


def nodes(root,kind):
    result=[]
    root.visit(lambda n:result.append(n) if str(n.kind)=='SyntaxKind.'+kind else None)
    return result


def identifiers(node):
    return {n.identifier.valueText for kind in ('IdentifierName','IdentifierSelectName') for n in nodes(node,kind)}


def ports(m):
    result={};direction='';dtype=''
    for p in m.header.ports.ports:
        if not hasattr(p,'declarator'):continue
        h=p.header
        if h is not None:
            if hasattr(h,'direction') and str(h.direction).strip():direction=h.direction.valueText
            if hasattr(h,'dataType') and str(h.dataType).strip():dtype=str(h.dataType).strip()
            elif hasattr(h,'direction') and str(h.direction).strip():dtype=''
        result[p.declarator.name.valueText]=(direction,re.sub(r'\b(reg|wire|logic)\b','',dtype).strip())
    return result


def parameters(m):
    ps=m.header.parameters
    if ps is None:return []
    result=[]
    for d in ps.declarations:
        if hasattr(d,'declarators'):
            result += [x.name.valueText for x in d.declarators if hasattr(x,'name')]
    return result


def span(n):return n.sourceRange.start.offset,n.sourceRange.end.offset


def plain(node):
    def strip(x):
        if isinstance(x,dict):return {k:strip(v) for k,v in x.items() if k!='trivia'}
        if isinstance(x,list):return [strip(v) for v in x]
        return x
    return strip(json.loads(node.to_json()))

def reorder_wrappers(source):
    """Avoid implicit nets by placing aggregates after their declarations."""
    tree=SyntaxTree.fromText(source);groups=defaultdict(list);edits=[]
    names={item[0] for group in GROUPS.values() for item in group}
    for n in nodes(module(tree)[0],'HierarchyInstantiation'):
        if n.type.valueText in names:groups[n.parent].append(n)
    for parent,items in groups.items():
        end=max(n.sourceRange.end.offset for n in parent.members if hasattr(n,'sourceRange'))
        for n in items:edits.append((*span(n),''))
        edits.append((end,end,'\n'+'\n'.join(source[a:b] for a,b in map(span,items))+'\n'))
    for a,b,text in sorted(edits,reverse=True):source=source[:a]+text+source[b:]
    return source


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    destination=ROOT/'native_motion/rtl/wrappers';destination.mkdir(exist_ok=True)
    if any(destination.glob('*.v')):raise FileExistsError('Wrapper generation already has outputs')
    pending=[]
    catalog={};trees=[]
    for path in (ROOT/'native_motion/rtl').rglob('*.v'):
        tree=SyntaxTree.fromFile(str(path));trees.append(tree)
        for m in module(tree):
            if m.header is not None:catalog[m.header.name.valueText]=m
    manifest=dict(schema='gesture.pl.structural_wrappers.v1',source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  hardware_changed=False,existing_bit_rebuilt=False,parents={},wrappers=[])
    for relative,groups in GROUPS.items():
        path=ROOT/'native_motion/rtl'/relative;source=path.read_text('utf-8');old=source
        tree=SyntaxTree.fromText(source);trees.append(tree);m=module(tree)[0];params=parameters(m)
        insts={n.instances[0].decl.name.valueText:n for n in nodes(m,'HierarchyInstantiation')}
        signals=ports(m);decls={}
        for n in nodes(m,'NetDeclaration')+nodes(m,'DataDeclaration'):
            dtype=re.sub(r'\b(reg|wire|logic)\b','',str(n.type)).strip()
            for d in n.declarators:
                if hasattr(d,'name'):
                    signals[d.name.valueText]=('local',dtype);decls[d.name.valueText]=(n,d)
        edits=[];moved_decls={};parent_rec=dict(before_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),wrappers=[])
        original_file=OUT/'before'/relative;original_file.parent.mkdir(parents=True,exist_ok=True)
        if original_file.exists() and original_file.read_bytes()!=path.read_bytes():raise ValueError('Original source changed')
        original_file.write_bytes(path.read_bytes())
        for wrapper,instance,names in groups:
            chosen=[insts[name] for name in names]
            # A wrapper cannot move an instance out of its generate condition.
            if len({(str(n.parent.kind),span(n.parent)) for n in chosen})!=1:raise ValueError('Different generate scopes: '+wrapper)
            used=set();drivers=set();connections=[]
            for n in chosen:
                definition=catalog[n.type.valueText];declared=ports(definition);ordered=list(declared)
                for i,c in enumerate(n.instances[0].connections):
                    if not hasattr(c,'expr') or c.expr is None:continue
                    # SeparatedSyntaxList also includes comma tokens.
                    name=c.name.valueText if hasattr(c,'name') else None
                    if name is None:
                        position=sum(hasattr(x,'expr') for x in list(n.instances[0].connections)[:i]);name=ordered[position]
                    ids=identifiers(c.expr)&signals.keys();used|=ids
                    if declared[name][0] in ('output','inout'):drivers|=ids
                    connections.append(dict(child=n.instances[0].decl.name.valueText,port=name,direction=declared[name][0],expression=str(c.expr).strip()))
            selected_text='\n'.join(old[a:b] for a,b in map(span,chosen))
            internal=[]
            for name in used:
                if name not in decls:continue
                n,d=decls[name]
                if d.initializer is not None:continue
                if len(re.findall(r'\b'+re.escape(name)+r'\b',old))==len(re.findall(r'\b'+re.escape(name)+r'\b',selected_text))+1:
                    internal.append(name);moved_decls[name]=wrapper
            external=sorted(used-set(internal))
            header=[('output' if name in drivers else 'input')+' wire '+signals[name][1]+' '+name for name in external]
            body=['wire '+signals[name][1]+' '+name+';' for name in sorted(internal)]
            body += [old[a:b] for a,b in map(span,chosen)]
            text='// Structural wrapper: original instances, parameters and cycles preserved.\n`timescale 1ns/1ps\n'
            text+='module '+wrapper+(str(m.header.parameters) if m.header.parameters else '')+'(\n    '+',\n    '.join(header)+'\n);\n'
            text+='\n'.join(body)+'\nendmodule\n'
            wp=destination/(wrapper+'.v');pending.append((wp,text))
            call=wrapper+(' #(\n    '+',\n    '.join('.'+p+'('+p+')' for p in params)+'\n)' if params else '')+' '+instance+'(\n    '+',\n    '.join('.'+p+'('+p+')' for p in external)+'\n);'
            for j,n in enumerate(chosen):edits.append((*span(n),call if j==0 else ''))
            rec=dict(file=wp.relative_to(ROOT).as_posix(),module=wrapper,instance=instance,parent=path.relative_to(ROOT).as_posix(),
                parent_module=m.header.name.valueText,children=names,parameters=params,ports=[dict(name=p,direction='output' if p in drivers else 'input',type=signals[p][1]) for p in external],
                internal_signals=sorted(internal),connections=connections,original_instances=[plain(n) for n in chosen],
                sha256=hashlib.sha256(text.encode()).hexdigest())
            manifest['wrappers'].append(rec);parent_rec['wrappers'].append(wrapper)
        for n in nodes(m,'NetDeclaration')+nodes(m,'DataDeclaration'):
            ds=[d for d in n.declarators if hasattr(d,'name')]
            if not any(d.name.valueText in moved_decls for d in ds):continue
            remaining=[str(d).strip() for d in ds if d.name.valueText not in moved_decls]
            text=(str(n.netType)+' '+str(n.type) if hasattr(n,'netType') else str(n.type))+' '+', '.join(remaining)+';' if remaining else ''
            edits.append((*span(n),text))
        for a,b,text in sorted(edits,reverse=True):source=source[:a]+text+source[b:]
        source=reorder_wrappers(source)
        pending.append((path,source))
        parent_rec['after_sha256']=hashlib.sha256(source.encode()).hexdigest();manifest['parents'][path.relative_to(ROOT).as_posix()]=parent_rec
    for path,text in pending:path.write_text(text,encoding='utf-8',newline='\n')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('STRUCTURAL_WRAPPERS_WRITTEN',len(manifest['wrappers']))


if __name__=='__main__':main()
