const patientDeltas=[-2.2241868e-5,-2.0681236e-5,-1.5934162e-5,-1.5680643e-5,-1.387818e-5,-1.214136e-5,-1.1904209e-5,-1.1109272e-5,-9.324733e-6,-8.783269e-6,-8.357523e-6,-7.916632e-6,-7.407272e-6,-6.879976e-6,-6.106297e-6,-5.418712e-6,-5.265458e-6,-5.113819e-6,-4.908892e-6,-4.393243e-6,-3.631359e-6,-3.143646e-6,-2.807499e-6,-2.793055e-6,-2.716493e-6,-2.015701e-6,-1.749449e-6,-1.290341e-6,-1.253571e-6,-1.072395e-6,-1.048146e-6,-9.98111e-7,-9.71552e-7,-9.69102e-7,-7.95327e-7,-7.4648e-7,-5.08234e-7,-4.76325e-7,1.10344e-7,4.7723e-7,6.65713e-7,6.67259e-7,7.31953e-7,7.64979e-7,1.128423e-6,1.361495e-6,1.967922e-6,2.390769e-6,3.138677e-6,3.968845e-6,5.57049e-6,6.336794e-6,7.329629e-6,7.502053e-6,7.981763e-6,8.369477e-6,9.95057e-6,1.1987423e-5,1.5648139e-5];
const targetDeltas=[["5-FU",-2.657559e-6],["AZD7762",-1.70363e-7],["Afatinib",4.90427e-6],["Alisertib",-9.325842e-6],["Atorvastatin",-1.517604e-6],["Bemcentinib",9.707693e-6],["Encorafenib",1.09432e-6],["Gedatolisib",-1.1525075e-5],["Gemcitabine",-1.3418363e-5],["Idasanutlin",3.610555e-6],["LCL161",4.396352e-6],["LGK974",-7.283623e-6],["Lapatinib",3.018221e-6],["Luminespib",-8.92316e-7],["Methotrexate",-5.840714e-6],["Napabucasin",-1.1881989e-5],["Palbociclib",-1.1465044e-5],["Panobinostat",-4.825341e-6],["Pevonedistat",-7.660139e-6],["Regorafenib",1.1347273e-5],["SN-38",3.4285e-7],["TAS-102",-5.598968e-6],["Trametinib",8.447e-9],["Volasertib",9.68447e-7]];

(function(){
  const host=document.getElementById('patientDeltaChart');
  if(!host)return;
  const W=720,H=250,p=30,max=Math.max(...patientDeltas.map(v=>Math.abs(v))),zero=H/2;
  const pts=patientDeltas.map((v,i)=>{
    const x=p+i*(W-2*p)/(patientDeltas.length-1);
    const y=zero-(v/max)*(H/2-p);
    return [x,y];
  });
  const poly=pts.map(([x,y])=>x.toFixed(1)+','+y.toFixed(1)).join(' ');
  const dots=pts.map(([x,y])=>'<circle cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" r="2.2"/>').join('');
  host.innerHTML='<svg class="delta-svg" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Sorted anonymized patient MSE differences versus the previous additive model"><line class="delta-zero" x1="'+p+'" x2="'+(W-p)+'" y1="'+zero+'" y2="'+zero+'"/><polyline class="delta-line" points="'+poly+'"/>'+dots+'</svg>';
})();

(function(){
  const host=document.getElementById('targetDeltaChart');
  if(!host)return;
  const ordered=[...targetDeltas].sort((a,b)=>a[1]-b[1]);
  const max=Math.max(...ordered.map(x=>Math.abs(x[1])));
  host.innerHTML=ordered.map(([name,v])=>{
    const half=(Math.abs(v)/max)*48;
    const left=v<0?50-half:50;
    const signed=(v*1e6).toFixed(2);
    return '<div class="target-delta-row"><span class="target-delta-name">'+name+'</span><div class="target-delta-axis"><i style="left:'+left+'%;width:'+half+'%"></i><b></b></div><code>'+signed+'e-6</code></div>';
  }).join('');
})();