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
      +'<path d="'+d+'" fill="none" stroke="#3fb27f" stroke-width="1.5"/></svg>'
      +'<div class="small">Last '+points.length+' runs · min '+min+' / max '+max+' tok/s</div>';
  }
};
