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
  diagnostics(){return this.get("/api/diagnostics")},
  models(){return this.get("/api/models")},
  async freeRam(){
    try{
      var r=await fetch("/api/memory/free",{method:"POST"});
      return await r.json();
    }catch(e){return {success:false,error:String(e)}}
  },
  async downloadModel(id){
    try{
      var r=await fetch("/api/models/download",{method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({id:id})});
      return await r.json();
    }catch(e){return {success:false,error:String(e)}}
  },
  async loadModel(id){
    try{
      var r=await fetch("/api/models/load",{method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({id:id})});
      return await r.json();
    }catch(e){return {success:false,error:String(e)}}
  },
  async unloadModel(id){
    try{
      var r=await fetch("/api/models/unload",{method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({id:id})});
      return await r.json();
    }catch(e){return {success:false,error:String(e)}}
  },
  async stopServer(){
    try{
      var r=await fetch("/api/server/stop",{method:"POST"});
      return await r.json();
    }catch(e){return {success:false,error:String(e)}}
  },
  async chat(messages,opts){
    try{
      var r=await fetch("/api/chat",{method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(Object.assign({messages:messages},opts||{}))});
      return await r.json();
    }catch(e){return {success:false,error:String(e)}}
  }
};
