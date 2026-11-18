// Vocabulary equivalence only: no entity IDs, device catalogue or cached values.
// Domain, area, protocol and device_class filters remain strict in the HA adapter.
const groups=[['pv','photovoltaique','photovolta','solar','solaire'],['temperature','temperatures','temp'],['humidity','humidite','hygrometrie'],['power','puissance'],['energy','energie'],['battery','batterie'],['consumption','consommation'],['production','generation'],['forecast','prevision','prediction']];
export function haTermsMatch(terms,text,{expand=true}={}){
 const words=text.split(' ');
 return terms.every(term=>{
  if(text.includes(term))return true;
  if(!expand)return false;
  const group=groups.find(g=>g.some(v=>v===term||(term.length>=5&&(v.startsWith(term)||term.startsWith(v)))));
  return group?.some(v=>words.some(w=>w===v||(v.length>=5&&w.startsWith(v))))||false;
 });
}
export function forecastPenalty(query,text){
 const isForecast=/\b(forecast|prevision\w*|prediction\w*|estim\w*|estimated)\b/;
 return !isForecast.test(query)&&isForecast.test(text)?100:0;
}
