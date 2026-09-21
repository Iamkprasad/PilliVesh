var API={
  async get(path){
    try{
      var r=await fetch(path,{cache:"no-store"});
      var j=await r.json();
      return j;
    }catch(e){return {success:false,error:String(e)}}
  },
  telemetry(){return this.get("/api/telemetry")},
  benchmark(){return this.get("/api/benchmark")},
  logs(f){return this.get("/api/logs?limit=100&type="+(f||"all"))},
  memory(q){return this.get("/api/memory?limit=20"+(q?("&q="+encodeURIComponent(q)):""))},
  skills(name){return this.get("/api/skills"+(name?("?name="+encodeURIComponent(name)):""))},
  tools(){return this.get("/api/tools")},
  tasks(){return this.get("/api/tasks")},
  diagnostics(){return this.get("/api/diagnostics")}
};
