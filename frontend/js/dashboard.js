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
  renderHome:function(t,b){
    var mem=(t.system&&t.system.memory)||{};
    var hw="";
    hw+=this.kv("CPU",(t.system&&t.system.cpu_cores!=null?t.system.cpu_cores+" Cores":"Not available"));
    hw+=this.kv("RAM",mem.total_mb!=null?(gb(mem.used_mb)+" / "+gb(mem.total_mb)):"Not available");
    hw+=this.kv("Available",mem.available_mb!=null?gb(mem.available_mb):"—");
    hw+=this.kv("SWAP",mem.swap_total_mb!=null?(gb(mem.swap_used_mb)+" / "+gb(mem.swap_total_mb)):"Not available");
    hw+=this.kv("GPU",t.gpu&&t.gpu.device?esc(shortGpu(t.gpu.device)):"Not installed");
    hw+=this.kv("Vulkan",t.gpu?(t.gpu.vulkan_available?"Available":"Not available"):"—");
    document.getElementById("hwGrid").innerHTML=hw;
    var rp=pct(mem.used_mb,mem.total_mb),sp=pct(mem.swap_used_mb,mem.swap_total_mb);
    document.getElementById("ramBar").style.width=rp+"%";
    document.getElementById("swapBar").style.width=sp+"%";
    document.getElementById("ramText").textContent=mem.total_mb!=null?(rp+"% · Avail "+gb(mem.available_mb)):"Not available";
    document.getElementById("swapText").textContent=mem.swap_total_mb!=null?(sp+"%"):"Not available";

    var temps=(t.system&&t.system.temperatures_c)||{};
    var th=this.thermalMap.map(function(g){
      var v=Dashboard.pickTemp(temps,g[1]);
      return Dashboard.kv(g[0],v==null?"—":v+"°C");
    }).join("");
    document.getElementById("thermGrid").innerHTML=th||Dashboard.kv("Thermals","Not available");

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
      bb.innerHTML=this.kv("Status","Waiting for model")+this.kv("Prompt speed","—")+this.kv("Generation speed","—")+this.kv("Latency","—")+this.kv("Model","Not installed");
      Charts.line(document.getElementById("benchChart"),[]);
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
    document.getElementById("gpuBox").textContent=((t.gpu&&t.gpu.raw)||"GPU info not available.")
      +"\nNote: the MiB figure reported by llama.cpp is shared/unified memory, not dedicated VRAM.";
    var sb=document.getElementById("settingsBox");
    if(sb){sb.innerHTML=
      this.kv("API host","127.0.0.1 (localhost only)")+
      this.kv("API port","8080")+
      this.kv("Refresh","5 s")+
      this.kv("Mode","Read-only");}
    if(diag){
      document.getElementById("diagBox").innerHTML=
        this.kv("Python",esc(diag.python||"—"))+
        this.kv("Models",diag.models&&diag.models.length?esc(diag.models.map(function(m){return m.name}).join(", ")):"None")+
        this.kv("profile.json",diag.files?"✓":"—");
      document.getElementById("diagBox2").innerHTML=document.getElementById("diagBox").innerHTML;
    }
  }
};
