var Dashboard={
  thermalMap:[
    ["CPU",["cpuss-0-usr","cpuss-1-usr","cpu-1-0-usr"]],
    ["GPU",["gpuss-1-usr","gpuss-0-usr","gpuss-max-step"]],
    ["Battery",["battery","qcom_battery","bms"]],
    ["Skin",["skin-therm-usr","skin-msm-therm-usr"]],
    ["DDR",["ddr-usr","ddr-step"]],
    ["NPU",["npu-usr","npu-step"]]
  ],
  pickTemp:function(all,keys){
    for(var i=0;i<keys.length;i++){if(all&&all[keys[i]]!=null)return all[keys[i]]}
    return null;
  },
  kv:function(k,v){return '<div class="kv"><span class="k">'+esc(k)+'</span><span class="v">'+v+'</span></div>'},
  formatMemory:function(content){
    var text=String(content||"");
    var parts=text.split(" | ");
    function field(name){
      for(var i=0;i<parts.length;i++){
        if(parts[i].indexOf(name+":")===0)return parts[i].slice(name.length+1).trim();
      }
      return null;
    }
    var task=field("Task"),tool=field("Tool"),verified=field("Verified");
    var payload=field("Facts"),label="Facts";
    if(payload==null){payload=field("Result");label="Result";}
    var out="";
    if(task)out+="<div><b>Task:</b> "+esc(task)+"</div>";
    if(tool)out+='<div class="meta"><span>Tool: '+esc(tool)+"</span>"+(verified?"<span>Verified: "+esc(verified)+"</span>":"")+"</div>";
    if(payload){
      if(payload.indexOf("'cpu_cores'")>=0){
        var facts=[],m;
        m=payload.match(/'cpu_cores':\s*(\d+)/);
        if(m)facts.push("CPU cores: "+m[1]);
        m=payload.match(/Mem:\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\S+)/);
        if(m)facts.push("RAM available: "+m[1]);
        m=payload.match(/Swap:\s+(\S+)\s+\S+\s+(\S+)/);
        if(m)facts.push("Swap total/free: "+m[1]+"/"+m[2]);
        m=payload.match(/Vulkan0:\s*(.+)\(/);
        if(m){var g=m[1].trim();facts.push("GPU: "+(g.indexOf("Adreno")>=0?"Adreno 650":g));facts.push("Backend: Vulkan");}
        out+='<div class="meta"><span>'+esc(label)+"</span></div><div>"+facts.map(function(f){return esc(f)}).join("<br>")+"</div>";
      }else if(payload.indexOf(";")>=0){
        out+='<div class="meta"><span>'+esc(label)+"</span></div><div>"+payload.split(";").map(function(s){return esc(s.trim())}).join("<br>")+"</div>";
      }else{
        out+="<div>"+esc(label+": "+payload)+"</div>";
      }
    }
    return out||esc(text);
  },
  renderHome:function(t,b){
    var mem=(t.system&&t.system.memory)||{};
    var cpuEl=document.getElementById("cpuVal");
    var ramEl=document.getElementById("ramVal");
    var ramSub=document.getElementById("ramSub");
    var gpuEl=document.getElementById("gpuVal");
    var gpuSub=document.getElementById("gpuSub");
    var modelEl=document.getElementById("modelVal");
    var modelSub=document.getElementById("modelSub");
    var ramBar=document.getElementById("ramBar");
    if(cpuEl)cpuEl.textContent=(t.system&&t.system.cpu_cores!=null?t.system.cpu_cores:"—");
    if(ramEl)ramEl.textContent=mem.total_mb!=null?(gb(mem.used_mb||0)+" / "+gb(mem.total_mb)):"—";
    if(ramSub)ramSub.textContent=mem.available_mb!=null?(gb(mem.available_mb)+" available"):"—";
    if(ramBar)ramBar.style.width=(mem.total_mb?Math.round((mem.used_mb||0)/mem.total_mb*100):0)+"%";
    if(gpuEl)gpuEl.textContent=(t.gpu&&t.gpu.device?shortGpu(t.gpu.device):"—");
    if(gpuSub)gpuSub.textContent=(t.gpu&&t.gpu.vulkan_available?"Vulkan":"—");
    if(modelEl)modelEl.textContent=(t.runtime&&t.runtime.model_downloaded?"Installed":"Not installed");
    if(modelSub)modelSub.textContent=(t.runtime&&t.runtime.llama_version||"—");

    document.getElementById("hwGrid").innerHTML=
      this.kv("CPU",(t.system&&t.system.cpu_cores!=null?t.system.cpu_cores+" Cores":"Not available"))+
      this.kv("RAM",mem.total_mb!=null?(gb(mem.used_mb)+" / "+gb(mem.total_mb)):"Not available")+
      this.kv("Available",mem.available_mb!=null?gb(mem.available_mb):"—")+
      this.kv("SWAP",mem.swap_total_mb!=null?(gb(mem.swap_used_mb)+" / "+gb(mem.swap_total_mb)):"Not available")+
      this.kv("GPU",t.gpu&&t.gpu.device?esc(shortGpu(t.gpu.device)):"Not installed")+
      this.kv("Vulkan",t.gpu?(t.gpu.vulkan_available?"Available":"Not available"):"—");

    var rt=t.runtime||{},bm=t.benchmark||{};
    var ver=(rt.llama_version||"Not available");
    var model=(rt.model_downloaded?"Installed":"Not installed");
    var benchStatus=(bm.status==="success"?"Done":(bm.status||"Waiting"));
    var ctx=(b&&b.runtime&&b.runtime.candidate_context_sizes)?b.runtime.candidate_context_sizes.join(" / "):"—";
    document.getElementById("runtimeGrid").innerHTML=
      this.kv("Backend",esc(rt.backend||"Not available"))+
      this.kv("GPU",esc(t.gpu&&t.gpu.device?shortGpu(t.gpu.device):"Not installed"))+
      this.kv("llama.cpp",esc(ver))+
      this.kv("Model",esc(model))+
      this.kv("Context",esc(ctx))+
      this.kv("Benchmark",esc(benchStatus));

    var bb=document.getElementById("benchBox");
    if(!b||b.status!=="success"){
      var waiting=(b&&b.status==="stale")?"Last run (no model loaded)":"Waiting for model";
      bb.innerHTML=this.kv("Status",waiting)+this.kv("Prompt speed","—")+this.kv("Generation speed","—")+this.kv("Latency","—")+this.kv("Model",esc((b&&b.model)||"—"));
      var hist0=((b&&b.history)||[]).map(function(r){return r.metrics&&r.metrics.generation_tokens_per_second}).filter(function(v){return v!=null});
      Charts.line(document.getElementById("benchChart"),hist0);
    }else{
      var m=b.metrics||{};
      bb.innerHTML=this.kv("Status","Success")+
        this.kv("Prompt",(m.prompt_tokens_per_second!=null?m.prompt_tokens_per_second+" tok/s":"—"))+
        this.kv("Generation",(m.generation_tokens_per_second!=null?m.generation_tokens_per_second+" tok/s":"—"))+
        this.kv("Latency",(b.elapsed_seconds!=null?(b.elapsed_seconds*1000).toFixed(0)+" ms":"—"))+
        this.kv("Model",esc(b.model||"—"));
      var hist=(b.history||[]).map(function(r){return r.metrics&&r.metrics.generation_tokens_per_second}).filter(function(v){return v!=null});
      Charts.line(document.getElementById("benchChart"),hist);
    }
  },
  renderRuntime:function(t,diag){
    var rt=t.runtime||{};
    document.getElementById("runtimeFull").innerHTML=
      this.kv("Backend",esc(rt.backend||"—"))+
      this.kv("llama.cpp",esc(rt.llama_version||"Not available"))+
      this.kv("Model",esc(rt.model_downloaded?"Installed":"Not installed"))+
      this.kv("CPU",esc(t.system&&t.system.cpu_cores!=null?t.system.cpu_cores+" cores":"—"))+
      this.kv("Updated",esc(fmtTime(t.timestamp)));
    var raw=(t.gpu&&t.gpu.raw)||"";
    var dev=(t.gpu&&t.gpu.device)||null;
    var shared=null,dm=raw.match(/Vulkan0:\s*(.+)\((\d+)\s*MiB/);
    if(dm){shared=dm[2]+" MiB";if(!dev)dev=dm[1].trim();}
    document.getElementById("gpuBox").innerHTML=
      this.kv("GPU",dev?esc(shortGpu(dev)):"Not installed")+
      this.kv("Vulkan",(t.gpu&&t.gpu.vulkan_available)?"Available":"Not available")+
      this.kv("Shared memory",shared||"—")+
      '<div class="small">Note: the MiB figure reported by llama.cpp is shared/unified memory, not dedicated VRAM.</div>'+
      '<details class="tech"><summary>Technical details</summary><div class="mono small">'+esc(raw||"GPU info not available.")+'</div></details>';
    var sb=document.getElementById("settingsBox");
    if(sb){sb.innerHTML=
      this.kv("API host","127.0.0.1 (localhost only)")+
      this.kv("API port","8080")+
      this.kv("Model port","8081")+
      this.kv("Refresh","5 s")+
      this.kv("Mode","Read-only + model load + chat");}
    if(diag){
      document.getElementById("diagBox").innerHTML=
        this.kv("Python",esc(diag.python||"—"))+
        this.kv("Models",diag.models&&diag.models.length?esc(diag.models.map(function(m){return m.name}).join(", ")):"0 installed")+
        this.kv("profile.json",diag.files?"✓":"—");
      document.getElementById("diagBox2").innerHTML=document.getElementById("diagBox").innerHTML;
    }
  }
};
