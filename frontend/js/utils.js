function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function gb(mb){if(mb==null||isNaN(mb))return "—";return (mb/1024).toFixed(1)+" GB"}
function pct(a,b){if(a==null||b==null||!b)return 0;return Math.max(0,Math.min(100,Math.round(a/b*100)))}
function fmtTime(iso){try{var d=new Date(iso);if(isNaN(d))return "—";return d.toLocaleTimeString([],{hour12:false})}catch(e){return "—"}}
function shortGpu(name){if(!name)return "Not installed";if(name.indexOf("Adreno")>=0)return "Adreno 650";return name}
