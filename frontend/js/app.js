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
    return "<div class='row'><div class='meta'><span>"+esc(m.type)+"</span><span>"+esc(m.created_at||"")+"</span></div><div>"+esc(m.content||"")+"</div></div>"}).join("")
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
refreshHome();
setInterval(function(){if(currentView==="home"||currentView==="runtime")refreshHome()},5000);
