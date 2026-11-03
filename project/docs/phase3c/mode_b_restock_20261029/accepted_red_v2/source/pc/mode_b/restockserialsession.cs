// Persistent supervised TTL transport. Original native samples are never
// regenerated, skipped, compressed into a catch-up burst, or retried.
using System;
using System.IO;
using System.IO.Ports;
using System.Text;
using System.Text.RegularExpressions;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;

namespace ModeB {
    public interface IRestockPort : IDisposable {
        void Open();
        string ReadAvailable();
        void WriteLine(string line);
        int BytesToWrite { get; }
    }
    public interface IRestockClock {
        double Milliseconds { get; }
        void Pause(int milliseconds);
    }
    public sealed class SerialRestockPort : IRestockPort {
        readonly SerialPort port;
        public SerialRestockPort(string name) {
            port = new SerialPort(name,115200,Parity.None,8,StopBits.One);
            port.Handshake=Handshake.None; port.DtrEnable=false; port.RtsEnable=false;
            port.NewLine="\n"; port.ReadTimeout=100; port.WriteTimeout=1500;
        }
        public void Open() { port.Open(); }
        public string ReadAvailable() { return port.ReadExisting(); }
        public void WriteLine(string value) { port.WriteLine(value); }
        public int BytesToWrite { get { return port.BytesToWrite; } }
        public void Dispose() { try { if(port.IsOpen) port.Close(); } finally { port.Dispose(); } }
    }
    public sealed class RestockClock : IRestockClock {
        readonly Stopwatch timer=Stopwatch.StartNew();
        public double Milliseconds { get { return timer.Elapsed.TotalMilliseconds; } }
        public void Pause(int ms) { Thread.Sleep(ms); }
    }
    public sealed class RestockSerialSession {
        [DllImport("winmm.dll")] static extern uint timeBeginPeriod(uint period);
        [DllImport("winmm.dll")] static extern uint timeEndPeriod(uint period);
        static readonly string[] axes={"b","s","e","t","r","g"};
        readonly JavaScriptSerializer json=new JavaScriptSerializer { MaxJsonLength=100000000, RecursionLimit=80 };
        readonly IRestockPort port;
        readonly IRestockClock clock;
        readonly string folder;
        readonly List<object> requests=new List<object>();
        readonly List<object> observations=new List<object>();
        readonly List<object> metrics=new List<object>();
        readonly List<string> completed=new List<string>();
        readonly StringBuilder pending=new StringBuilder();
        Dictionary<string,object> latest;
        double received=-100000, lastQuery=-100000;
        long generation=0;
        StreamWriter rx, tx;
        bool releaseRequested, releaseObserved, serialClosed;
        string status="STARTED", error;
        int queryCount;
        double timeoutMs=2000, queryPeriodMs=100;

        public RestockSerialSession(IRestockPort p, IRestockClock c, string output) {
            port=p; clock=c; folder=output;
        }
        static Dictionary<string,object> Map(object value) { return (Dictionary<string,object>)value; }
        static double Number(object value) { return Convert.ToDouble(value, System.Globalization.CultureInfo.InvariantCulture); }
        static double Get(Dictionary<string,object> map,string key) { return Number(map[key]); }
        static bool Flag(Dictionary<string,object> map,string key) {
            if(!map.ContainsKey(key)) return false;
            return map[key] is bool ? (bool)map[key] : Number(map[key])!=0;
        }
        public static Dictionary<string,object> ParseState(string raw) {
            // Uppercase T is the message type; lowercase t is the wrist.
            // Reject duplicate required fields instead of accepting last wins.
            string[] required={"T","b","s","e","t","r","g","x","y","z","tit"};
            foreach(string key in required)
                if(Regex.Matches(raw,"\""+key+"\"\\s*:").Count!=1) return null;
            Dictionary<string,object> state;
            try { state=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(raw); }
            catch { return null; }
            foreach(string key in required) {
                object value=state[key];
                if(value==null || value is string || value is bool) return null;
                double n;
                try { n=Number(value); } catch { return null; }
                if(double.IsNaN(n) || double.IsInfinity(n)) return null;
            }
            double type=Get(state,"T");
            if(type!=-15 && type!=1051) return null;
            return state;
        }
        void Receive() {
            string part=port.ReadAvailable();
            if(!String.IsNullOrEmpty(part)) pending.Append(part);
            if(pending.Length>1048576) throw new IOException("Oversize TTL receive frame");
            while(true) {
                string text=pending.ToString(); int index=text.IndexOf('\n');
                if(index<0) break;
                string raw=text.Substring(0,index).Trim(); pending.Remove(0,index+1);
                rx.WriteLine(json.Serialize(new {elapsed_ms=clock.Milliseconds,raw_json=raw}));
                Dictionary<string,object> state=ParseState(raw);
                if(state==null) continue;
                if(Flag(state,"Stalltor") || Flag(state,"Stalltep") || Flag(state,"Stallvol"))
                    throw new IOException("TTL firmware fault; no following motion");
                foreach(string key in new[]{"torswitchB","torswitchS","torswitchE","torswitchT","torswitchR","torswitchG"})
                    if(state.ContainsKey(key) && Get(state,key)!=1)
                        throw new IOException("Joint torque disabled; no following motion");
                latest=state; received=clock.Milliseconds; generation++;
            }
        }
        void Poll(bool requireFresh) {
            if(File.Exists(Path.Combine(folder,"STOP_REQUESTED")))
                throw new IOException("Operator software stop requested; no following motion");
            Receive();
            if(clock.Milliseconds-lastQuery>=queryPeriodMs) {
                port.WriteLine("{\"T\":105}"); lastQuery=clock.Milliseconds; queryCount++;
                Receive();
            }
            if(requireFresh && (latest==null || clock.Milliseconds-received>timeoutMs))
                throw new IOException("TTL feedback stale; no following motion");
        }
        void Until(double due) {
            do {
                Poll(true);
                double left=due-clock.Milliseconds;
                if(left<=0) return;
                clock.Pause((int)Math.Max(1,Math.Min(5,Math.Ceiling(left))));
            } while(true);
        }
        double Submit(string label,string wire) {
            Poll(true);
            // Refuse a congested link, without accumulating a burst of moves.
            if(port.BytesToWrite>512) throw new IOException("TTL output backpressure; no following motion");
            var row=new Dictionary<string,object> {
                {"label",label},{"wire_json",wire},{"attempted_utc",DateTimeOffset.UtcNow.ToString("o")},
                {"elapsed_ms",clock.Milliseconds},{"response",null}
            };
            requests.Add(row);
            // Persist intent before writing. A write exception has an unknown
            // device outcome, so this request remains attempted and is not retried.
            tx.WriteLine(json.Serialize(row)); tx.Flush();
            double wireStart=clock.Milliseconds;
            port.WriteLine(wire);
            row["wire_started_ms"]=wireStart;
            row["write_duration_ms"]=clock.Milliseconds-wireStart;
            row["response"]="TTL_WRITE_RETURNED_EXECUTION_NOT_ACKNOWLEDGED";
            return wireStart;
        }
        double[] Joints() {
            double[] q=new double[6]; for(int i=0;i<6;i++) q[i]=Get(latest,axes[i]); return q;
        }
        double[] Values(object value) {
            var a=(IList)value; double[] output=new double[a.Count];
            for(int i=0;i<a.Count;i++) output[i]=Number(a[i]); return output;
        }
        List<double[]> Observe(string label,double settleMs,int count,int spacingMs,double[] target) {
            Until(clock.Milliseconds+settleMs);
            List<double[]> states=new List<double[]>();
            double start=clock.Milliseconds, last=-100000; long seen=generation;
            List<object> samples=new List<object>();
            while(states.Count<count) {
                Poll(true);
                if(generation>seen && clock.Milliseconds-last>=spacingMs) {
                    double[] q=Joints(); states.Add(q);
                    var savedFeedback=new Dictionary<string,object>(latest);
                    savedFeedback["message_type"]=savedFeedback["T"]; savedFeedback.Remove("T");
                    samples.Add(new {elapsed_ms=clock.Milliseconds,joint_rad=q,feedback=savedFeedback});
                    last=clock.Milliseconds; seen=generation;
                }
                if(clock.Milliseconds-start>5000) throw new IOException("Incomplete boundary feedback");
                clock.Pause(2);
            }
            double[] residual=new double[6]; double[] actual=states[states.Count-1];
            if(target!=null) for(int i=0;i<6;i++) residual[i]=(actual[i]-target[i])*180/Math.PI;
            observations.Add(new {label=label,samples=samples,joint_error_deg=residual,
                residual_stop_enabled=false,arrival_accepted=false});
            return states;
        }
        void Save(Dictionary<string,object> session) {
            var result=new Dictionary<string,object> {
                {"schema","gesture.mode_b.restock_session_result.v1"},{"status",status},{"error",error},
                {"plan_file",session["plan_file"]},{"plan_sha256",session["plan_sha256"]},
                {"session_wire_sha256",session["ordered_wire_lf_sha256"]},
                {"transport","PERSISTENT_TTL_SERIAL"},{"requests",requests},{"motion_requests",requests.Count},
                {"observations",observations},{"completed_stages",completed},{"timing",metrics},
                {"queries",queryCount},{"release_requested",releaseRequested},{"release_observed",releaseObserved},
                {"inventory_restored",status=="RESTOCK_SEQUENCE_FINISHED_PHYSICAL_REVIEW_REQUIRED"},
                {"physical_restock_confirmed",false},{"residual_stop_enabled",false},{"no_motion_retry",true},
                {"serial_closed",serialClosed},{"elapsed_ms",clock.Milliseconds},
                {"final_firmware_rad",latest==null ? null : Joints()}
            };
            File.WriteAllText(Path.Combine(folder,"RESTOCK_RESULT.json"),json.Serialize(result),new UTF8Encoding(false));
            rx.Flush(); tx.Flush();
        }
        public void Run(string sessionJson) {
            Dictionary<string,object> session=json.Deserialize<Dictionary<string,object>>(sessionJson);
            if((string)session["schema"]!="gesture.mode_b.restock_serial_session.v1") throw new ArgumentException("Session schema");
            Directory.CreateDirectory(folder);
            rx=new StreamWriter(Path.Combine(folder,"SERIAL_RX.jsonl"),false,new UTF8Encoding(false),65536);
            tx=new StreamWriter(Path.Combine(folder,"REQUESTS.jsonl"),false,new UTF8Encoding(false),65536);
            timeoutMs=Get(session,"feedback_timeout_ms"); queryPeriodMs=Get(session,"query_period_ms");
            bool fineTimer=clock is RestockClock && timeBeginPeriod(1)==0;
            try {
                port.Open();
                double start=clock.Milliseconds;
                while(latest==null) {
                    Poll(false); if(clock.Milliseconds-start>4000) throw new IOException("No current TTL feedback; no motion");
                    clock.Pause(5);
                }
                double[] desired=Values(session["start"]), limits=Values(session["entry_limits_deg"]);
                List<double[]> entry=Observe("RESTOCK_PRE",0,5,200,desired);
                for(int i=0;i<6;i++) {
                    double min=entry[0][i],max=min;
                    foreach(double[] q in entry) { min=Math.Min(min,q[i]); max=Math.Max(max,q[i]); }
                    if((max-min)*180/Math.PI>.5) throw new IOException("Entry still moving; no motion");
                    if(Math.Abs(entry[entry.Count-1][i]-desired[i])*180/Math.PI>limits[i])
                        throw new IOException("Entry pose mismatch at "+axes[i]+"; no motion");
                }
                foreach(object value in (IList)session["operations"]) {
                    var op=Map(value); string label=(string)op["label"];
                    double begin=clock.Milliseconds; double[] target;
                    if((string)op["kind"]=="event") {
                        target=Joints(); double startHand=target[5]; target[5]=Get(op,"target_g");
                        if(label.StartsWith("RELEASE_")) releaseRequested=true;
                        Submit(label,(string)((IList)op["wires"])[0]);
                        // Preserve the previously accepted servo travel estimate
                        // and1s margin; contact residual alone never blocks lift.
                        double dwell=Math.Abs(target[5]-startHand)*4096/(2*Math.PI)/Get(op,"gripper_spd")*1000+1000;
                        Until(clock.Milliseconds+dwell);
                    } else {
                        IList wires=(IList)op["wires"]; double period=Get(op,"period_ms");
                        double next=clock.Milliseconds; double first=0,previous=0,maxInterval=0;
                        for(int i=0;i<wires.Count;i++) {
                            Until(next); double sent=Submit(label,(string)wires[i]);
                            if(i==0) first=sent; else maxInterval=Math.Max(maxInterval,sent-previous);
                            // The20ms period includes a blocking serial write.
                            // Use write START, rather than write RETURN, as the
                            // timestamp. Waiting20ms after a14ms write would
                            // accidentally produce a34ms wire cadence.
                            // A write longer than one period stretches time;
                            // no concurrent writes or compressed catch-up.
                            previous=sent; next=Math.Max(begin+(i+1)*period,sent+period);
                        }
                        Until(next);
                        metrics.Add(new {label=label,frames=wires.Count,nominal_ms=wires.Count*period,
                            submission_ms=clock.Milliseconds-first,max_interframe_ms=maxInterval});
                        target=Values(op["target"]);
                    }
                    Observe(label,Get(op,"settle_ms"),3,100,target);
                    completed.Add(label);
                    if(label.StartsWith("RELEASE_")) releaseObserved=true;
                    Save(session);
                    Console.WriteLine("SESSION_STAGE_FINISHED: "+label);
                }
                if(requests.Count!=(int)Number(session["requests"])) throw new IOException("Incomplete sequence");
                status="RESTOCK_SEQUENCE_FINISHED_PHYSICAL_REVIEW_REQUIRED";
            } catch(Exception e) {
                status="STOPPED_NO_FURTHER_REQUESTS"; error=e.Message; throw;
            } finally {
                try { port.Dispose(); serialClosed=true; }
                finally {
                    try { Save(session); rx.Dispose(); tx.Dispose(); }
                    finally { if(fineTimer) timeEndPeriod(1); }
                }
            }
        }
    }
}
