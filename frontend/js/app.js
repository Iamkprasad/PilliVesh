var currentView="home",logFilter="all",memTimer=null;
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
        +"<button class='chip' data-unload='"+esc(m.id)+"'"+(modelBusy?" disabled":"")+">Unload</button>";
    }else{
      actions="<button class='chip' data-load='"+esc(m.id)+"'"+(modelBusy?" disabled":"")+">Load</button>";
    }
    var stateTags="<span class='tag model'>INSTALLED</span>";
    if(!m.installed)stateTags="";
    var routerTag=routerUp?"<span class='tag tool'>ROUTER UP</span>":"";
    return "<div class='row'><b>"+esc(m.name)+"</b> <span class='tag'>"+esc(m.quant)+"</span> "+stateTags+" "+routerTag
      +"<div class='meta'><span>~"+esc(m.size_mb)+" MB</span><span>needs "+esc(m.min_ram_mb)+" MB free RAM</span><span>ctx "+esc(m.context)+"</span></div>"
      +"<div>"+esc(m.notes||"")+"</div>"
      +(pctDl!=null?"<div class='bar'><div class='bar-fill' style='width:"+pctDl+"%'></div></div>":"")
      +"<div class='model-actions' style='margin-top:6px'>"+actions+"</div></div>";
  }).join("");
  if(dl.status==="error")html="<div class='row'><div class='meta'><span class='tag error'>ERROR</span></div><div>"+esc(dl.error||"download failed")+"</div></div>"+html;
  var ops=document.getElementById("modelOpsResult");
  box.innerHTML=html||"<div class='row'>No models in catalog.</div>";
  box.querySelectorAll("[data-dl]").forEach(function(b){
    b.onclick=function(){API.downloadModel(b.getAttribute("data-dl")).then(function(){refreshModels()})};
  });
  box.querySelectorAll("[data-load]").forEach(function(b){
    b.onclick=function(){runModelOp("load",b.getAttribute("data-load"))};
  });
  box.querySelectorAll("[data-unload]").forEach(function(b){
    b.onclick=function(){runModelOp("unload",b.getAttribute("data-unload"))};
  });
  clearTimeout(dlTimer);
  if(dl.status==="downloading")dlTimer=setTimeout(refreshModels,2000);
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
  if(v==="more")refreshMore();
  if(v==="runtime")refreshHome();
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
document.querySelectorAll("#themeRow .theme-chip").forEach(function(b){
  b.onclick=function(){applyTheme(b.getAttribute("data-theme"))};
});
try{
  applyTheme(localStorage.getItem("pv-theme")||"green");
}catch(e){applyTheme("green")}
var refreshTimer=setInterval(function(){if(currentView==="home"||currentView==="runtime")refreshHome()},5000);
document.getElementById("stopBtn").onclick=function(){
  if(!confirm("Stop the PilliVesh server and close the port?"))return;
  API.stopServer().then(function(){
    clearInterval(refreshTimer);clearTimeout(dlTimer);
    document.getElementById("statusText").textContent="■ Server stopped";
    document.getElementById("updateLine").textContent="Port closed. Restart with ./run-dashboard.sh";
  });
};
refreshHome();
