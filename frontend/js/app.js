var currentView="home",logFilter="all",memTimer=null;
var chatHistory=[],chatBusy=false;
function setStatus(t,online){
  var dot=document.querySelector("#statusLine .dot"),txt=document.getElementById("statusText"),up=document.getElementById("updateLine");
  dot.className="dot "+(!t?"unknown":(!online?"bad":((t.runtime&&t.runtime.model_downloaded)?"ok":((t.gpu&&t.gpu.vulkan_available)?"ok":"warn"))));
  if(!t){txt.textContent="○ Telemetry offline";up.textContent="No data";return}
  var modelDL=t.runtime&&t.runtime.model_downloaded;
  if(modelDL)txt.textContent="● Runtime Online";
  else if(t.gpu&&t.gpu.vulkan_available)txt.textContent="● Runtime Online (no model)";
  else txt.textContent="● Runtime Degraded";
  up.textContent=(online?"● LIVE · Updated ":"⚠ OFFLINE · Last ")+fmtTime(t.timestamp);
}
async function refreshHome(){
  var tr=await API.telemetry(),br=await API.benchmark();
  if(tr.success){State.setTelemetry(tr.data);setStatus(tr.data,true);Dashboard.renderHome(tr.data,br.success?br.data:null)}
  else{State.online=false;setStatus(State.telemetry,false);
    if(!State.telemetry){document.getElementById("hwGrid").innerHTML="<div class='small'>Telemetry unavailable</div>"}}
  if(br.success){var dr=await API.diagnostics();Dashboard.renderRuntime(State.telemetry||{},dr.success?dr.data:null)}
}
async function refreshLogs(){
  var r=await API.logs(logFilter);
  var box=document.getElementById("logList");
  if(!r.success){box.innerHTML="<div class='row'>Logs unavailable: "+esc(r.error)+"</div>";return}
  var recs=(r.data&&r.data.records)||[];
  if(!recs.length){box.innerHTML="<div class='row'>No events.</div>";return}
  box.innerHTML=recs.slice(0,60).map(function(e){
    var ev=String(e.event||"event"),cls=ev.indexOf("tool")>=0?"tool":(/error|fail/i.test(ev)?"error":(/model|benchmark/i.test(ev)?"model":""));
    return "<div class='row' tabindex='0'><div class='meta'><span>"+esc(fmtTime(e.timestamp))+"</span><span class='tag "+cls+"'>"+esc(ev.toUpperCase())+"</span></div>"
      +"<div>"+esc((e.data&&(e.data.message||e.data.summary))||JSON.stringify(e.data||{}).slice(0,160))+"</div>"
      +"<pre>"+esc(JSON.stringify(e,null,2).slice(0,2000))+"</pre></div>";
  }).join("");
  box.querySelectorAll(".row").forEach(function(el){el.onclick=function(){el.classList.toggle("open")}});
}
async function refreshMemory(q){
  var r=await API.memory(q);
  var cbox=document.getElementById("memCounts"),box=document.getElementById("memList");
  if(!r.success){cbox.innerHTML="";box.innerHTML="<div class='row'>Memory unavailable: "+esc(r.error)+"</div>";return}
  var c=r.data.counts||{};
  cbox.innerHTML=["procedural","semantic","episodic","project"].map(function(k){
    return "<span class='chip'>"+k+": "+(c[k]!=null?c[k]:"—")+"</span>"}).join("");
  var items=r.data.items||[];
  box.innerHTML=items.length?items.map(function(m){
    return "<div class='row'><div class='meta'><span>"+esc(m.type)+"</span><span>"+esc(m.created_at||"")+"</span></div><div>"+Dashboard.formatMemory(m.content)+"</div></div>"}).join("")
    :"<div class='row'>No memories found.</div>";
}
async function refreshMore(){
  var s=await API.skills();
  document.getElementById("skillsBox").innerHTML=s.success?(s.data.skills||[]).map(function(x){
    return "<div class='row' data-skill='"+esc(x.name)+"'><b>"+esc(x.title)+"</b><div class='meta'>"+esc(x.name)+"</div><pre></pre></div>"}).join("")
    :"<div class='row'>Skills unavailable</div>";
  document.querySelectorAll("#skillsBox .row").forEach(function(el){
    el.onclick=function(){
      API.skills(el.getAttribute("data-skill")).then(function(r){
        if(r.success){el.querySelector("pre").textContent=r.data.content.slice(0,4000);el.classList.add("open")}});
    }});
  var t=await API.tools();
  document.getElementById("toolsBox").innerHTML=t.success?(t.data.tools||[]).map(function(x){
    return "<div class='row'><b>"+esc(x.name)+"</b><div class='meta'>Available</div><div>"+esc(x.description||"")+"</div></div>"}).join("")
    :"<div class='row'>Tools unavailable</div>";
  var tk=await API.tasks();
  if(tk.success){
    var a=tk.data.active||[];
    document.getElementById("tasksBox").innerHTML=a.length?a.map(function(x){
      return "<div class='row'><b>"+esc(x.project)+"</b><div>"+esc(x.title)+"</div><div class='meta'><span>"+esc(x.status||"active")+"</span><span>"+esc(x.notes||"")+"</span></div></div>"}).join("")
      :"<div class='row'>No active tasks.</div>";
  }else document.getElementById("tasksBox").innerHTML="<div class='row'>Tasks unavailable</div>";
  refreshModels();
}
var dlTimer=null,modelBusy=false;
async function refreshModels(){
  var box=document.getElementById("modelsBox");
  if(!box)return;
  var r=await API.models();
  if(!r.success){box.innerHTML="<div class='row'>Models unavailable: "+esc(r.error)+"</div>";return}
  var dl=r.data.download||{status:"idle"};
  var routerUp=!!r.data.router_running;
  var html=(r.data.catalog||[]).map(function(m){
    var pctDl=null;
    if(dl.status==="downloading"&&dl.model_id===m.id&&dl.bytes_total){
      pctDl=Math.min(99,Math.round(dl.bytes_done/dl.bytes_total*100));
    }
    var actions;
    if(!m.installed){
      actions=(dl.status==="downloading"&&dl.model_id===m.id)
        ?"<span class='tag tool'>DOWNLOADING "+(pctDl!=null?pctDl+"%":"…")+"</span>"
        :"<button class='chip' data-dl='"+esc(m.id)+"'>Download</button>";
    }else if(m.loaded){
      actions="<span class='tag resident'>RESIDENT</span> "
        +"<button class='chip' data-unload='"+esc(m.id)+"'"+(modelBusy?" disabled":"")+">Unload</button> "
        +"<button class='chip' data-bench='"+esc(m.id)+"'>Bench</button>";
    }else{
      actions="<button class='chip' data-load='"+esc(m.id)+"'"+(modelBusy?" disabled":"")+">Load</button>";
    }
    var stateTags="<span class='tag model'>INSTALLED</span>";
    if(!m.installed)stateTags="";
    var routerTag=routerUp?"<span class='tag tool'>ROUTER UP</span>":"";
    var stats=m.stats||null;
    var statsLine="";
    if(stats&&stats.runs){
      statsLine="<div class='model-stats-line'>"
        +"<span class='stat hot'>AVG "+esc(stats.avg_generation_tps)+" t/s</span>"
        +"<span class='stat'>MIN "+esc(stats.min_generation_tps)+" · MAX "+esc(stats.max_generation_tps)+"</span>"
        +"<span class='stat'>"+esc(stats.runs)+" RUNS</span>"
        +"<span class='stat'>LAST "+esc(fmtTime(stats.last))+"</span>"
        +"</div>";
    }else if(m.installed){
      statsLine="<div class='model-stats-line'><span class='stat'>NO BENCH YET</span></div>";
    }
    var details="";
    if(stats&&stats.runs){
      var rows=(stats.recent||[]).map(function(s){
        return "<tr><td>"+esc(fmtTime(s.timestamp))+"</td>"
          +"<td>"+esc(s.generation_tokens_per_second!=null?s.generation_tokens_per_second:"—")+"</td>"
          +"<td>"+esc(s.prompt_tokens_per_second!=null?s.prompt_tokens_per_second:"—")+"</td>"
          +"<td>"+esc(s.elapsed_seconds!=null?s.elapsed_seconds+"s":"—")+"</td></tr>";
      }).join("");
      details="<div class='model-details'>"
        +"<div class='spark-wrap' data-spark='"+esc(m.id)+"'></div>"
        +"<table><thead><tr><th>When</th><th>Gen t/s</th><th>Prompt t/s</th><th>Latency</th></tr></thead>"
        +"<tbody>"+rows+"</tbody></table>"
        +"<div class='small' style='margin-top:6px'>avg latency "
        +esc(stats.avg_latency_ms!=null?stats.avg_latency_ms+" ms":"—")
        +" · avg prompt "+esc(stats.avg_prompt_tps!=null?stats.avg_prompt_tps+" t/s":"—")+"</div>"
        +"</div>";
    }
    var expand=stats&&stats.runs
      ?"<button class='stat-toggle' data-expand='"+esc(m.id)+"'>Details</button>":"";
    return "<div class='row' data-model-row='"+esc(m.id)+"'><b>"+esc(m.name)+"</b> <span class='tag'>"+esc(m.quant)+"</span> "+stateTags+" "+routerTag
      +"<div class='meta'><span>~"+esc(m.size_mb)+" MB</span><span>needs "+esc(m.min_ram_mb)+" MB free RAM</span><span>ctx "+esc(m.context)+"</span></div>"
      +"<div>"+esc(m.notes||"")+"</div>"
      +statsLine
      +(pctDl!=null?"<div class='bar'><div class='bar-fill' style='width:"+pctDl+"%'></div></div>":"")
      +"<div class='model-actions' style='margin-top:6px'>"+actions+"</div>"
      +expand+details+"</div>";
  }).join("");
  if(dl.status==="error")html="<div class='row'><div class='meta'><span class='tag error'>ERROR</span></div><div>"+esc(dl.error||"download failed")+"</div></div>"+html;
  var ops=document.getElementById("modelOpsResult");
  box.innerHTML=html||"<div class='row'>No models in catalog.</div>";
  // Sparklines for expanded cards (rendered hidden until open).
  (r.data.catalog||[]).forEach(function(m){
    if(m.stats&&m.stats.spark&&m.stats.spark.length){
      var host=box.querySelector("[data-spark='"+m.id+"']");
      if(host)Charts.line(host,m.stats.spark);
    }
  });
  box.querySelectorAll("[data-expand]").forEach(function(btn){
    btn.onclick=function(){
      var row=btn.closest(".row");
      if(row)row.classList.toggle("open");
    };
  });
  box.querySelectorAll("[data-dl]").forEach(function(b){
    b.onclick=function(){API.downloadModel(b.getAttribute("data-dl")).then(function(){refreshModels()})};
  });
  box.querySelectorAll("[data-load]").forEach(function(b){
    b.onclick=function(){runModelOp("load",b.getAttribute("data-load"))};
  });
  box.querySelectorAll("[data-unload]").forEach(function(b){
    b.onclick=function(){runModelOp("unload",b.getAttribute("data-unload"))};
  });
  box.querySelectorAll("[data-bench]").forEach(function(b){
    b.onclick=function(){runBenchFor(b.getAttribute("data-bench"),b)};
  });
  clearTimeout(dlTimer);
  if(dl.status==="downloading")dlTimer=setTimeout(refreshModels,2000);
}
async function refreshStatsPanel(){
  var box=document.getElementById("statsBox");
  var sum=document.getElementById("statsSummary");
  if(!box)return;
  var r=await API.models();
  if(!r.success){
    if(sum)sum.textContent="Stats unavailable: "+(r.error||"");
    return;
  }
  var cat=r.data.catalog||[];
  var withRuns=cat.filter(function(m){return m.stats&&m.stats.runs});
  if(sum){
    sum.textContent=withRuns.length
      ? (withRuns.length+" model(s) with efficiency data · resident: "
         +((r.data.loaded_ids||[])[0]||"none"))
      : "No efficiency samples yet. Load a model and press Bench (or wait for the auto-probe).";
  }
  box.innerHTML=cat.map(function(m){
    var s=m.stats||{};
    var has=!!s.runs;
    var kv=[
      ["Avg gen",has?s.avg_generation_tps+" t/s":"—"],
      ["Min/Max",has?(s.min_generation_tps+" / "+s.max_generation_tps+" t/s"):"—"],
      ["Avg prompt",has&&s.avg_prompt_tps!=null?s.avg_prompt_tps+" t/s":"—"],
      ["Avg latency",has&&s.avg_latency_ms!=null?s.avg_latency_ms+" ms":"—"],
      ["Runs",has?String(s.runs):"0"],
      ["Last",has?fmtTime(s.last):"—"],
      ["Size","~"+m.size_mb+" MB"],
      ["State",m.loaded?"Resident":(m.installed?"Installed":"Not installed")]
    ].map(function(p){
      return "<div class='kv'><span class='k'>"+esc(p[0])+"</span><span class='v'>"+esc(p[1])+"</span></div>";
    }).join("");
    var spark=has&&s.spark&&s.spark.length
      ?"<div class='spark-wrap' data-stat-spark='"+esc(m.id)+"'></div>"
      :"<div class='small'>No samples yet.</div>";
    return "<div class='row'><b>"+esc(m.name)+"</b> <span class='tag'>"+esc(m.quant)+"</span>"
      +(m.loaded?" <span class='tag resident'>RESIDENT</span>":"")
      +"<div class='kv-grid' style='margin-top:6px'>"+kv+"</div>"
      +spark
      +(m.loaded?"<div class='model-actions' style='margin-top:6px'><button class='chip' data-bench2='"+esc(m.id)+"'>Bench now</button></div>":"")
      +"</div>";
  }).join("")||"<div class='row'>No models in catalog.</div>";
  cat.forEach(function(m){
    if(m.stats&&m.stats.spark&&m.stats.spark.length){
      var host=box.querySelector("[data-stat-spark='"+m.id+"']");
      if(host)Charts.line(host,m.stats.spark);
    }
  });
  box.querySelectorAll("[data-bench2]").forEach(function(b){
    b.onclick=function(){runBenchFor(b.getAttribute("data-bench2"),b).then(function(){refreshStatsPanel()})};
  });
}
function modelOpsOut(){
  return document.getElementById("modelOpsResult");
}
async function runModelOp(op,id){
  if(modelBusy)return;
  var out=modelOpsOut();
  if(op==="load"){
    if(!confirm("Load this model into RAM? (only one resident; loading another swaps)"))return;
  }else{
    if(!confirm("Unload this model? The inference process stops to save battery."))return;
  }
  modelBusy=true;
  refreshModels();
  if(out){out.innerHTML="<span class='small'>… "+esc(op.toUpperCase())+"ING "+esc(id)+"</span>"}
  try{
    var r=op==="load"?await API.loadModel(id):await API.unloadModel(id);
    if(!r.success){
      if(out)out.innerHTML="<span class='err-text'>[ERR] "+esc(op)+" failed: "+esc(r.error||"unknown")+"</span>";
    }else{
      var d=r.data||{};
      var msg=op==="load"
        ?"[OK] "+esc(id)+" resident (pid "+esc(String(d.pid||"?"))+")"
        :"[OK] "+esc(id)+" unloaded"+(d.router_stopped?" — router stopped":"");
      if(out)out.innerHTML="<span class='ok-text'>"+msg+"</span>";
    }
  }catch(e){
    if(out)out.innerHTML="<span class='err-text'>[ERR] "+esc(String(e))+"</span>";
  }
  modelBusy=false;
  refreshModels();
  if(op==="load"||op==="unload")refreshHome();
}
async function runBenchFor(id,btn){
  var out=document.getElementById("modelOpsResult")||document.getElementById("benchResult");
  var prev=btn?btn.textContent:null;
  if(btn){btn.disabled=true;btn.textContent="…"}
  if(out)out.textContent="Running light probe…";
  try{
    var r=await API.runBenchmark(id);
    if(!r.success){
      if(out)out.innerHTML="<span class='err-text'>[ERR] "+esc(r.error||"probe failed")+"</span>";
      return null;
    }
    var d=r.data||{};
    if(d.status==="in_progress"){
      if(out)out.textContent=d.message||"Probe already running…";
      return d;
    }
    if(d.status==="success"){
      var m=d.metrics||{};
      if(out)out.innerHTML="<span class='ok-text'>[OK] gen "
        +esc(m.generation_tokens_per_second!=null?m.generation_tokens_per_second+" t/s":"—")
        +" · prompt "+esc(m.prompt_tokens_per_second!=null?m.prompt_tokens_per_second+" t/s":"—")
        +" · "+esc(d.elapsed_seconds!=null?d.elapsed_seconds+"s":"")+"</span>";
    }else{
      if(out)out.innerHTML="<span class='err-text'>[ERR] "+esc(d.message||d.status||"probe failed")+"</span>";
    }
    refreshHome();
    refreshModels();
    return d;
  }catch(e){
    if(out)out.innerHTML="<span class='err-text'>[ERR] "+esc(String(e))+"</span>";
    return null;
  }finally{
    if(btn){btn.disabled=false;btn.textContent=prev||"Bench"}
  }
}
async function refreshChatStatus(){
  var el=document.getElementById("chatStatus");
  if(!el)return;
  var r=await API.models();
  if(!r.success){el.innerHTML="<span class='err-text'>Cannot check model status</span>";return}
  var running=!!r.data.router_running;
  var loaded=(r.data.loaded_ids||[])[0]||null;
  if(running&&loaded){
    el.innerHTML="<span class='ok-text'>● Model loaded: "+esc(loaded)+" — ready to chat</span>";
  }else if(running){
    el.innerHTML="<span class='tag warn'>Router up</span> but no model resident. Load one in More → Models.";
  }else{
    el.innerHTML="<span class='err-text'>No model loaded.</span> Go to <b>More → Models</b> and press <b>Load</b> first.";
  }
}
function chatStamp(){
  try{return new Date().toLocaleTimeString([],{hour12:false})}catch(e){return ""}
}
function renderChat(){
  var box=document.getElementById("chatMessages");
  if(!box)return;
  if(!chatHistory.length){
    box.innerHTML="<div class='chat-empty'>"
      +"<div class='hero'>[ LOCAL MODEL ]</div>"
      +"<div>No messages yet.</div>"
      +"<div class='hint'>Responses stream live from llama-server on :8081. Enter sends · Shift+Enter newline.</div>"
      +"</div>";
    return;
  }
  box.innerHTML=chatHistory.map(function(m,i){
    var who=m.role==="user"?"You":(m.role==="assistant"?"Model":"System");
    var cls="chat-msg "+esc(m.role)+(m.error?" error":"");
    var stamp=m.t||"";
    return "<div class='"+cls+"' data-i='"+i+"'>"
      +"<div class='msg-head'><span class='who'>"+esc(who)+"</span>"
      +(stamp?"<span class='stamp'>"+esc(stamp)+"</span>":"")
      +"</div>"
      +"<div class='body'>"+esc(m.content||"")+"</div>"
      +(m.role==="assistant"&&m.content?"<div class='msg-actions'><button class='copy-btn' data-copy='"+i+"'>Copy</button></div>":"")
      +"</div>";
  }).join("");
  box.querySelectorAll("[data-copy]").forEach(function(b){
    b.onclick=function(){
      var i=+b.getAttribute("data-copy");
      var m=chatHistory[i];
      if(!m)return;
      try{navigator.clipboard.writeText(m.content||"")}catch(e){}
      b.textContent="Copied";
      setTimeout(function(){b.textContent="Copy"},1200);
    };
  });
  box.scrollTop=box.scrollHeight;
}
function upsertStreamBubble(){
  var box=document.getElementById("chatMessages");
  if(!box)return null;
  var el=document.getElementById("chatStreaming");
  if(el)return el;
  // If empty-state is showing, clear it.
  if(!chatHistory.length||box.querySelector(".chat-empty"))chatHistory=[];
  var div=document.createElement("div");
  div.className="chat-msg assistant";
  div.id="chatStreaming";
  div.innerHTML="<div class='msg-head'><span class='who'>Model</span>"
    +"<span class='stamp'>"+esc(chatStamp())+"</span></div>"
    +"<div class='body'><span class='typing-dots'><i></i><i></i><i></i></span><span class='stream-caret'></span></div>";
  box.appendChild(div);
  box.scrollTop=box.scrollHeight;
  return div;
}
function setStreamText(el,text,done){
  if(!el)return;
  var body=el.querySelector(".body");
  if(!body)return;
  if(!text&&!done){
    body.innerHTML="<span class='typing-dots'><i></i><i></i><i></i></span><span class='stream-caret'></span>";
    return;
  }
  body.textContent=text;
  if(!done){
    var caret=document.createElement("span");
    caret.className="stream-caret";
    body.appendChild(caret);
  }
  var box=document.getElementById("chatMessages");
  if(box)box.scrollTop=box.scrollHeight;
}
async function sendChat(){
  if(chatBusy)return;
  var input=document.getElementById("chatInput");
  var btn=document.getElementById("chatSendBtn");
  var meta=document.getElementById("chatMeta");
  var text=(input.value||"").trim();
  if(!text)return;
  input.value="";
  chatHistory.push({role:"user",content:text,t:chatStamp()});
  if(chatHistory.length>100)chatHistory=chatHistory.slice(-100);
  renderChat();
  chatBusy=true;
  if(btn){btn.disabled=true;btn.classList.add("busy");btn.textContent="…"}
  if(meta)meta.textContent="connecting to local model…";
  var streamEl=upsertStreamBubble();
  setStreamText(streamEl,"");
  var acc="";
  try{
    var resp=await API.chatStream(chatHistory.slice(-20),{max_tokens:512,temperature:0.7});
    var ctype=(resp.headers&&resp.headers.get("content-type"))||"";
    if(!resp.ok){
      var errText="HTTP "+resp.status;
      try{var ej=await resp.json();errText=ej.error||errText}catch(e2){}
      throw new Error(errText);
    }
    if(ctype.indexOf("ndjson")>=0&&resp.body&&resp.body.getReader){
      var reader=resp.body.getReader();
      var dec=new TextDecoder();
      var buf="";
      while(true){
        var chunk=await reader.read();
        if(chunk.done)break;
        buf+=dec.decode(chunk.value,{stream:true});
        var lines=buf.split("\n");
        buf=lines.pop();
        for(var li=0;li<lines.length;li++){
          var line=lines[li].trim();
          if(!line)continue;
          try{
            var obj=JSON.parse(line);
          }catch(e3){continue}
          if(obj.t==="d"&&obj.c){
            acc+=obj.c;
            setStreamText(streamEl,acc,false);
            if(meta)meta.textContent="streaming · "+acc.length+" chars";
          }else if(obj.t==="error"){
            throw new Error(obj.e||"stream error");
          }
        }
      }
    }else{
      // Fallback: non-stream JSON
      var j=await resp.json();
      if(!j.success)throw new Error(j.error||"request failed");
      var choice=(j.data&&j.data.choices&&j.data.choices[0])||{};
      acc=(choice.message&&choice.message.content)||"";
      setStreamText(streamEl,acc,true);
    }
    if(streamEl)streamEl.remove();
    if(!acc)acc="[empty response]";
    chatHistory.push({role:"assistant",content:acc,t:chatStamp()});
    if(chatHistory.length>100)chatHistory=chatHistory.slice(-100);
    renderChat();
    if(meta)meta.textContent="done · "+acc.length+" chars";
  }catch(e){
    if(streamEl)streamEl.remove();
    var err=String((e&&e.message)||e);
    chatHistory.push({role:"assistant",content:"[error] "+err,t:chatStamp(),error:true});
    renderChat();
    if(meta)meta.innerHTML="<span class='err-text'>"+esc(err)+"</span>";
  }finally{
    chatBusy=false;
    if(btn){btn.disabled=false;btn.classList.remove("busy");btn.textContent="Send"}
  }
}
function openLlamaUI(){
  var url="http://127.0.0.1:8081";
  API.models().then(function(r){
    if(r.success&&r.data.router_running){
      var w=window.open(url,"_blank");
      if(w)w.opener=null;
    }else{
      alert("No model loaded.\n\nGo to More → Models and press Load first, then try again.");
    }
  });
}
async function exportReport(){
  var t=await API.telemetry(),d=await API.diagnostics();
  var L=[];
  L.push("# PilliVesh diagnostics report");
  if(t.success){var s=t.data.system||{},mem=s.memory||{};
    L.push("Date: "+t.data.timestamp);
    L.push("CPU: "+(s.cpu_cores!=null?s.cpu_cores+" cores":"n/a"));
    L.push("RAM: "+mem.used_mb+"/"+mem.total_mb+" MB (avail "+mem.available_mb+")");
    L.push("Swap: "+mem.swap_used_mb+"/"+mem.swap_total_mb+" MB");
    L.push("GPU: "+((t.data.gpu||{}).device||"n/a")+" Vulkan="+((t.data.gpu||{}).vulkan_available));
    L.push("llama.cpp: "+((t.data.runtime||{}).llama_version||"n/a"));
  }
  if(d.success){L.push("Python: "+d.data.python);
    L.push("Models: "+((d.data.models||[]).map(function(m){return m.name}).join(", ")||"0 installed"));}
  var text=L.join("\n");
  try{await navigator.clipboard.writeText(text);alert("Report copied to clipboard.");}
  catch(e){
    var a=document.createElement("a");
    a.href=URL.createObjectURL(new Blob([text],{type:"text/plain"}));
    a.download="pillivesh-diagnostics.txt";a.click();
  }
}
async function freeRam(){
  var btn=document.getElementById("freeRamBtn"),out=document.getElementById("freeRamResult");
  if(!confirm("Run best-effort RAM cleanup? (flush pages, release model cache, kill stale inferencers, ask Android to clear background processes)"))return;
  btn.disabled=true;btn.textContent="Cleaning…";out.textContent="";
  var r=await API.freeRam();
  btn.disabled=false;btn.textContent="Free up RAM";
  if(!r.success){out.innerHTML="<span class='err-text'>[ERR] Cleanup failed: "+esc(r.error)+"</span>";return}
  var d=r.data||{},acts=d.actions||[];
  var freed=d.freed_mb;
  var head=freed==null?"Cleanup finished (memory delta unavailable)":
    (freed>=0?"Freed ~"+freed+" MB available RAM":"Available RAM changed by "+freed+" MB (kernel may reclaim slowly)");
  var lines=acts.map(function(a){
    return (a.ok?"✓ ":"✗ ")+esc(a.name)+(a.detail?(" — "+esc(a.detail)):"");
  }).join("<br>");
  out.innerHTML="<b>"+esc(head)+"</b><br>"+lines;
  refreshHome();
}
function applyTheme(name){
  var allowed={green:1,pink:1,yellow:1,blue:1,red:1};
  if(!allowed[name])name="green";
  document.documentElement.setAttribute("data-theme",name);
  try{localStorage.setItem("pv-theme",name)}catch(e){}
  document.querySelectorAll("#themeRow .theme-chip").forEach(function(b){
    b.classList.toggle("on",b.getAttribute("data-theme")===name);
  });
  var m=document.querySelector('meta[name="theme-color"]');
  if(m)m.setAttribute("content","#0a0a0a");
}
function show(v){
  currentView=v;
  document.querySelectorAll(".view").forEach(function(s){s.classList.remove("active")});
  document.getElementById("view-"+v).classList.add("active");
  document.querySelectorAll(".tab").forEach(function(b){b.classList.toggle("on",b.getAttribute("data-view")===v)});
  if(v==="logs")refreshLogs();
  if(v==="memory")refreshMemory(document.getElementById("memSearch").value);
  if(v==="more"){refreshMore();refreshStatsPanel()}
  if(v==="runtime")refreshHome();
  if(v==="chat")refreshChatStatus();
}
document.querySelectorAll(".tab").forEach(function(b){b.onclick=function(){show(b.getAttribute("data-view"))}});
document.querySelectorAll("[data-goto]").forEach(function(b){b.onclick=function(){
  var g=b.getAttribute("data-goto");
  document.getElementById("more-"+(g==="diagnostics"?"diag":g)).scrollIntoView({behavior:"smooth"});
}});
document.querySelectorAll("#logFilters .chip").forEach(function(b){b.onclick=function(){
  document.querySelectorAll("#logFilters .chip").forEach(function(x){x.classList.remove("on")});
  b.classList.add("on");logFilter=b.getAttribute("data-f");refreshLogs()}});
document.getElementById("memSearch").addEventListener("input",function(e){
  clearTimeout(memTimer);memTimer=setTimeout(function(){refreshMemory(e.target.value)},350)});
document.getElementById("exportBtn").onclick=function(){exportReport()};
document.getElementById("freeRamBtn").onclick=function(){freeRam()};
document.getElementById("chatSendBtn").onclick=function(){sendChat()};
document.getElementById("openLlamaUiBtn").onclick=function(){openLlamaUI()};
document.getElementById("runBenchBtn").onclick=function(){
  var btn=document.getElementById("runBenchBtn");
  var out=document.getElementById("benchResult");
  btn.disabled=true;btn.textContent="Running…";
  if(out)out.textContent="Probing resident model…";
  API.runBenchmark(null).then(function(r){
    btn.disabled=false;btn.textContent="Run benchmark";
    if(!r.success){
      if(out)out.innerHTML="<span class='err-text'>[ERR] "+esc(r.error||"failed")+"</span>";
      return;
    }
    var d=r.data||{};
    if(d.status==="success"){
      var m=d.metrics||{};
      if(out)out.innerHTML="<span class='ok-text'>[OK] gen "
        +esc(m.generation_tokens_per_second!=null?m.generation_tokens_per_second+" t/s":"—")
        +" · prompt "+esc(m.prompt_tokens_per_second!=null?m.prompt_tokens_per_second+" t/s":"—")+"</span>";
    }else{
      if(out)out.innerHTML="<span class='err-text'>[ERR] "+esc(d.message||d.status||"failed")+"</span>";
    }
    refreshHome();
  }).catch(function(e){
    btn.disabled=false;btn.textContent="Run benchmark";
    if(out)out.innerHTML="<span class='err-text'>[ERR] "+esc(String(e))+"</span>";
  });
};
document.getElementById("clearChatBtn").onclick=function(){
  if(!chatHistory.length)return;
  if(!confirm("Clear the conversation?"))return;
  chatHistory=[];renderChat();
};
document.getElementById("chatInput").addEventListener("keydown",function(e){
  if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendChat()}
});
renderChat();
document.querySelectorAll("#themeRow .theme-chip").forEach(function(b){
  b.onclick=function(){applyTheme(b.getAttribute("data-theme"))};
});
try{
  applyTheme(localStorage.getItem("pv-theme")||"green");
}catch(e){applyTheme("green")}
var refreshTimer=setInterval(function(){
  if(currentView==="home"||currentView==="runtime")refreshHome();
  if(currentView==="more")refreshModels();
},5000);
document.getElementById("stopBtn").onclick=function(){
  if(!confirm("Stop the PilliVesh server and close the port?"))return;
  API.stopServer().then(function(){
    clearInterval(refreshTimer);clearTimeout(dlTimer);
    document.getElementById("statusText").textContent="■ Server stopped";
    document.getElementById("updateLine").textContent="Port closed. Restart with ./run-dashboard.sh";
  });
};
refreshHome();
