var State={telemetry:null,benchmark:null,lastUpdate:null,online:false,
  setTelemetry(t){this.telemetry=t;if(t&&t.timestamp){this.lastUpdate=t.timestamp;this.online=true}}};
