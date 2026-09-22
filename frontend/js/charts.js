var Charts={
  line:function(el,points){
    if(!el)return;
    if(!points||!points.length){el.innerHTML='<div class="small">No history yet.</div>';return}
    var w=300,h=64,p=6;
    var max=Math.max.apply(null,points),min=Math.min.apply(null,points);
    if(max===min)max=min+1;
    var step=(w-p*2)/Math.max(1,points.length-1);
    var d=points.map(function(v,i){
      var x=(p+i*step).toFixed(1);
      var y=(h-p-(v-min)/(max-min)*(h-p*2)).toFixed(1);
      return (i?"L":"M")+x+" "+y;
    }).join(" ");
    el.innerHTML='<svg viewBox="0 0 '+w+' '+h+'" width="100%" height="'+h+'" role="img">'
      +'<path d="'+d+'" fill="none" stroke="var(--primary)" stroke-width="1.5"/></svg>'
      +'<div class="small">Last '+points.length+' runs · min '+min+' / max '+max+' tok/s</div>';
  },
  multi:function(el,series,unit){
    if(!el)return;
    series=(series||[]).map(function(s){
      return {name:s.name,color:s.color,values:(s.values||[]).filter(function(v){return v!=null})};
    }).filter(function(s){return s.values.length>1});
    if(!series.length){el.innerHTML='<div class="small">Collecting history…</div>';return}
    var w=300,h=72,p=6,n=Math.max.apply(null,series.map(function(s){return s.values.length}));
    var all=[];series.forEach(function(s){all=all.concat(s.values)});
    var max=Math.max.apply(null,all),min=Math.min.apply(null,all);
    if(max===min)max=min+1;
    var step=(w-p*2)/(n-1);
    function path(vals){
      return vals.map(function(v,i){
        var x=(p+i*step).toFixed(1);
        var y=(h-p-(v-min)/(max-min)*(h-p*2)).toFixed(1);
        return (i?"L":"M")+x+" "+y;
      }).join(" ");
    }
    var svg='<svg viewBox="0 0 '+w+' '+h+'" width="100%" height="'+h+'" role="img">';
    series.forEach(function(s){svg+='<path d="'+path(s.values)+'" fill="none" stroke="'+s.color+'" stroke-width="1.5"/>';});
    svg+="</svg>";
    var legend=series.map(function(s){
      var last=s.values[s.values.length-1];
      return '<span style="color:'+s.color+'">'+esc(s.name)+' '+last+(unit||"")+'</span>';
    }).join(" · ");
    el.innerHTML=svg+'<div class="small">'+legend+'</div>';
  }
};
