"""Export measured session metrics; missing physical/ground-truth data stay NOT_RUN."""
import argparse
import csv
import datetime
import json
import math
from pathlib import Path
import statistics


def read(path):
    return [json.loads(s) for s in path.read_text('utf-8').splitlines() if s.strip()] if path.exists() else []


def quantiles(values):
    values=sorted(float(x) for x in values if math.isfinite(float(x)))
    if not values:return None
    def p(q):
        x=(len(values)-1)*q;a=int(x);b=min(a+1,len(values)-1)
        return values[a]*(1-(x-a))+values[b]*(x-a)
    return dict(n=len(values),p50=p(.5),p95=p(.95),p99=p(.99),max=values[-1])


def key(d):
    return tuple(d.get(k) for k in ('done_counter','restocked_tasks','cancelled_counter'))


def main(folder,out):
    out.mkdir(parents=True,exist_ok=False)
    telemetry=read(folder/'telemetry.jsonl');vision=read(folder/'vision.jsonl');comm=read(folder/'communication.jsonl')
    observations=read(folder/'operator_observations.jsonl');events=read(folder/'tasks.jsonl')
    completions={}
    for a,b in zip(telemetry,telemetry[1:]):
        if b.get('done_counter')!=a.get('done_counter') or b.get('restocked_tasks')!=a.get('restocked_tasks'):
            completions[key(b)]=b
    labels={key(r['control']['device']):r for r in observations if key(r.get('control',{}).get('device',{})) in completions}
    success=sum(r['physical_success'] is True for r in labels.values())
    physical=read(folder/'physical_latency.jsonl')
    physical=[r['sensor_to_physical_response_ms'] for r in physical if r.get('source')=='FIELD_MEASUREMENT'
              and r.get('sensor_start_definition') and r.get('physical_response_definition') and r.get('clock_or_video_method')]
    detector=[view['timing_ms'] for row in vision for view in row.get('detector',{}).get('spatial_views',[])]
    surface=[view['timing_ms'] for row in vision for view in row.get('surface_passes',[])]
    duration=(datetime.datetime.fromisoformat(telemetry[-1]['timestamp'])-datetime.datetime.fromisoformat(telemetry[0]['timestamp'])).total_seconds() if len(telemetry)>1 else None
    gaps=[(b['capture_started_monotonic']-a['capture_started_monotonic'])*1000 for a,b in zip(vision,vision[1:])]
    result=dict(schema='gesture.mode_ab.session_metrics.v1',program_completions=len(completions),
        physical_task_success=dict(annotated=len(labels),successes=success,
            success_rate_annotated_only=success/len(labels) if labels else None,coverage=len(labels)/len(completions) if completions else None,
            status='FIELD_ANNOTATED_SUBSET' if labels else 'NOT_RUN'),
        sensor_to_physical_response_ms=quantiles(physical),
        detector_per_pass_ms={k:quantiles(r[k] for r in detector) for k in ('preprocess','model','decode_nms')},
        surface_per_crop_ms={k:quantiles(r[k] for r in surface) for k in ('preprocess','model','postprocess')},
        total_perception_ms=quantiles(r['total_ms'] for r in vision),
        communication_roundtrip_ms=quantiles(r['roundtrip_ms'] for r in comm),
        communication_failure_rate=sum(not r['ok'] for r in comm)/len(comm) if comm else None,
        sustained_vision_fps=(len(vision)-1)/(vision[-1]['capture_started_monotonic']-vision[0]['capture_started_monotonic']) if len(vision)>1 else None,
        inference_output_gap_ms=quantiles(gaps),session_duration_s=duration,
        ai_quality='NOT_COMPUTED_WITHOUT_INDEPENDENT_GROUND_TRUTH',
        fpga_physical_latency='SEE_PL_TRACE_AND_SCOPE_LOG; UART_COMMAND_IS_NOT_PHYSICAL_RESPONSE',
        clock_policy='PC metrics use perf_counter/monotonic; PL trace uses its own 100 MHz-derived counter; no synchronized cross-clock one-way claim')
    (out/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    rows=[['任务闭环成功率（已标注子集）','核心',result['physical_task_success']['success_rate_annotated_only'],'ratio','现场程序完成与人工观察逐项匹配',len(labels),'operator_observations.jsonl'],
          ['端到端物理响应延迟','核心',json.dumps(result['sensor_to_physical_response_ms']),'ms','独立物理响应测量；无数据保持 NOT_RUN',len(physical),'physical_latency.jsonl'],
          ['总感知延迟 batch=1','核心',json.dumps(result['total_perception_ms']),'ms','普通RGB原图；ROCm；各阶段见metrics.json',len(vision),'vision.jsonl'],
          ['PC-FPGA RTT','核心',json.dumps(result['communication_roundtrip_ms']),'ms','JTAG MMIO请求至返回；同一PC单调时钟',len(comm),'communication.jsonl'],
          ['持续视觉处理帧率','专项',result['sustained_vision_fps'],'fps','采集线程取最新帧；非相机原生FPS',len(vision),'vision.jsonl'],
          ['连续会话时长','专项',duration,'s','实际遥测开始至结束；故障见原始日志',len(telemetry),'telemetry.jsonl']]
    with (out/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['指标名称','类别','数值','单位','测量条件','测试次数或时长','证据文件'])
        writer.writerows([[('NOT_RUN' if v is None or v=='null' else v) for v in row] for row in rows])
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.session,a.out)
