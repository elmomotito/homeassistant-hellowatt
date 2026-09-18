/** Hello Watt — Coût quotidien. Carte autonome Lovelace, sans dépendance externe.
 * type: custom:hello-watt-cost-card
 * Sources : attributs jours / mois / annees et archives sensor.hello_watt_historique_YYYY.
 * energy.hw_history_entities permet de choisir explicitement les archives d'un logement.
 * Pas de conversion kWh × tarif ; euros et kWh viennent du collecteur Hello Watt.
 * Les capteurs instantanés personnels ne sont jamais utilisés sans configuration explicite.
 */
(() => {
if(customElements.get('hello-watt-cost-card'))return;
const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
class HelloWattCostCard extends HTMLElement {
 constructor(){super();this.attachShadow({mode:'open'});this._cfg={energy:{}};this._recapPeriod='m';this._recapUnit='eur';this._anchor=null;this._selected=null;this.shadowRoot.addEventListener('click',e=>{const b=e.target.closest('button[data-action]');if(!b)return;const a=b.dataset.action;if(a==='unit')this._recapUnit=b.dataset.value;if(a==='period')this._recapPeriod=b.dataset.value;if(a==='nav'){const c=this.cursor();const d=new Date(c.y+(this._recapPeriod==='y'?Number(b.dataset.value):0),c.m+(this._recapPeriod==='m'?Number(b.dataset.value):0),1);this._anchor={y:d.getFullYear(),m:d.getMonth()};}if(a==='bar'){this._selected=Number(b.dataset.value);this.render();return;}this._selected=null;this.render();});}
 setConfig(c){if(c.injection_mode&&!['auto','paid','free','none'].includes(c.injection_mode))throw Error("injection_mode : auto, paid, free ou none");if(c.period&&!['month','year'].includes(c.period))throw Error('period : month ou year');if(c.unit&&!['eur','kwh'].includes(c.unit))throw Error('unit : eur ou kwh');if(c.theme&&!['auto','dark','light'].includes(c.theme))throw Error('theme : auto, dark ou light');this._cfg={...c,energy:{...(c.energy||{})}};this._recapPeriod=c.period==='year'?'y':'m';this._recapUnit=c.unit||'eur';this.render();}
 set hass(h){this._hass=h;this.render();}
 connectedCallback(){this.render();}
 static getStubConfig(){return {type:'custom:hello-watt-cost-card'};}
 getCardSize(){return 6;}
 getGridOptions(){return {columns:12,rows:7,min_columns:6,min_rows:5};}
 _st(id){return this._hass?.states?.[id];}
 _num(id,fallback=null){const n=this._hwValue(this._st(id)?.state);return n==null?fallback:n;}
 _hwEnt(key,fallback){return this._cfg.energy[key]||(key.startsWith('today_')?'':fallback);}
 cursor(){const d=new Date();return this._anchor||{y:d.getFullYear(),m:d.getMonth()};}
 render(){if(!this._hass)return;const c=this.cursor(),s=this._recapPeriod==='y'?this._hwYearSeries(c.y):this._hwSeries(c.y,c.m),tariffs=this._tariffData(s),tempo=tariffs.map,inj=this._injectionState(s);const light=this._cfg.theme==='light'||(this._cfg.theme!=='dark'&&this._hass.themes?.darkMode===false);const fmt=n=>n==null?'—':Number(n).toLocaleString('fr-FR',{maximumFractionDigits:this._recapUnit==='eur'?2:1,minimumFractionDigits:this._recapUnit==='eur'?2:0});const title=s.period==='y'?String(c.y):new Date(c.y,c.m,1).toLocaleDateString('fr-FR',{month:'long',year:'numeric'});const now=new Date();const atNow=c.y>now.getFullYear()||(c.y===now.getFullYear()&&(s.period==='y'||c.m>=now.getMonth()));const palette=tariffs.palette;let hasTempo=false;
 const bars=s.days.map((d,i)=>{let row=tempo[d.key]?{...tempo[d.key]}:null;if(row&&s.period==='y')for(const color of ['red','white','blue'])row['Tempo-'+color]=(row['Tempo-'+color+'-HP']||0)+(row['Tempo-'+color+'-HC']||0);const parts=row?palette.filter(([k])=>row[k]>0):[];const sum=parts.reduce((n,[k])=>n+row[k],0);const valid=parts.length&&d.cost!=null&&Math.abs(sum-d.cost)<=Math.max(.02,d.cost*1e-7)&&!d.est;hasTempo ||= !!valid;const up=d.cost==null?0:d.cost/s.maxUp*170,down=d.income==null?0:d.income/s.maxDown*44;const tip=`${d.key} · ${s.legCost} : ${fmt(d.cost)} ${s.u} · ${s.legInc} : ${fmt(d.income)} ${s.u}`;return `<button class="day ${d.future?'future':''} ${this._selected===i?'selected':''}" data-action="bar" data-value="${i}" aria-label="${esc(tip)}" title="${esc(tip)}"><span class="up"><span class="stack ${d.est?'estimated':''}" style="height:${up}px">${valid?parts.map(([key,label,color])=>`<i style="flex:${row[key]};background:${color}" title="${esc(label)} : ${fmt(row[key])} ${s.u}"></i>`).join(''):''}</span></span><span class="down"><span class="export ${d.est?'estimated':''}" style="height:${down}px"></span></span><span class="label">${d.label}</span></button>`}).join('');
 const money=this._recapUnit==='eur';const showExport=inj.mode!=='none'&&!(money&&inj.mode==='free');
 const fnum=n=>n==null?'—':Number(n).toLocaleString('fr-FR',{maximumFractionDigits:1});
 let stats=[[s.statCost,fmt(s.monthCost),s.u,'cost'],[s.statInc,fmt(s.monthInc),s.u,'income'],[s.statNet,fmt(s.monthCost!=null&&s.monthInc!=null?s.monthCost-s.monthInc:null),s.u,'net']];
 if(inj.mode==='free')stats=[[s.statCost,fmt(s.monthCost),s.u,'cost'],['Énergie injectée',fnum(inj.kwh),'kWh','income']];
 if(inj.mode==='none')stats=[[s.statCost,fmt(s.monthCost),s.u,'cost'],[s.period==='y'?'Moyenne mensuelle':'Moyenne quotidienne',fmt(s.avgCost),s.u,'net']];
 const pick=this._selected==null?null:s.days[this._selected];const count=s.days.filter(d=>d.cost!=null||d.income!=null).length;const detail=pick?`${pick.key} · ${s.legCost} : ${fmt(pick.cost)} ${s.u} · ${s.legInc} : ${inj.mode==='none'||(money&&inj.mode==='free')?'0':fmt(pick.income)} ${s.u}`:`${count} ${s.period==='y'?'mois':'jours'} disponibles${s.estDay?' · estimation du jour incluse':''}`;
 const chip=(a,v,label,on)=>`<button class="chip ${on?'active':''}" data-action="${a}" data-value="${v}" aria-pressed="${on}">${label}</button>`;
 const html=`<style>${CSS}</style><ha-card class="${light?'light':'dark'}"><header><div class="heading"><span class="icon">ϟ</span><div><div class="eyebrow">HELLO WATT</div><h2>${s.title}</h2></div></div><div class="controls"><div class="switch">${chip('unit','eur','€',this._recapUnit==='eur')}${chip('unit','kwh','kWh',this._recapUnit==='kwh')}</div><div class="switch">${chip('period','m','Mois',s.period==='m')}${chip('period','y','Année',s.period==='y')}</div></div></header><div class="subhead"><p>${this._recapUnit==='eur'?'Électricité importée, abonnement inclus':'Électricité importée et injectée'}</p><div class="navigate"><button data-action="nav" data-value="-1" aria-label="Période précédente">‹</button><strong>${title}</strong><button data-action="nav" data-value="1" aria-label="Période suivante" ${atNow?'disabled':''}>›</button></div></div><div class="context"><span>${esc(tariffs.contract)}</span><span>${esc(inj.label)}</span></div><div class="stats" style="grid-template-columns:repeat(${stats.length},minmax(0,1fr))">${stats.map(([label,n,u,cl])=>`<div class="stat ${cl}"><span>${label}</span><div>${n} <small>${u}</small></div></div>`).join('')}</div><section class="graph ${showExport?'':'no-export'}"><div class="legend"><span><i style="background:var(--blue)"></i>${s.legCost}</span>${showExport?`<span><i style="background:var(--pink)"></i>${s.legInc}</span>`:''}</div>${hasTempo?`<div class="legend tempo">${palette.map(([,label,color])=>`<span><i style="background:${color}"></i>${label}</span>`).join('')}</div>`:''}${!s.hasData?'<div class="empty">Aucune donnée Hello Watt pour cette période.<small>La carte attend les attributs d’historique des capteurs du collecteur.</small></div>':`<div class="chart-scroll"><div class="chart"><div class="axis"><span>${fmt(s.maxUp)} ${s.u}</span><span>0</span>${showExport?`<span>−${fmt(s.maxDown)} ${s.u}</span>`:''}</div><div class="plot"><div class="gridlines"><i></i><i></i><i></i></div><div class="average" style="top:${170-s.avgCost/s.maxUp*170}px" title="Moyenne import : ${fmt(s.avgCost)} ${s.u}"></div>${showExport?`<div class="average avg-export" style="top:${170+s.avgInc/s.maxDown*44}px" title="Moyenne injection : ${fmt(s.avgInc)} ${s.u}"></div>`:''}<div class="bars">${bars}</div></div></div></div>`}${s.hasData?`<div class="mean-legend"><span>Moy. import : ${fmt(s.avgCost)} ${s.u}/${s.period==='y'?'mois':'j'}</span>${showExport?`<span>Moy. injection : ${fmt(s.avgInc)} ${s.u}/${s.period==='y'?'mois':'j'}</span>`:''}</div>`:''}<footer aria-live="polite"><span>${esc(detail)}</span><span>Source : Hello Watt</span></footer></section></ha-card>`;
 if(html===this._lastHTML)return;const scroll=this.shadowRoot.querySelector('.chart-scroll')?.scrollLeft||0;this.shadowRoot.innerHTML=html;const el=this.shadowRoot.querySelector('.chart-scroll');if(el&&scroll)el.scrollLeft=scroll;this._lastHTML=html;
 }
_tariffData(s) {
 const prefix=String(s.y)+(s.period==='y'?'-':'-'+String(s.m+1).padStart(2,'0')+'-'),daily={};
 for(const attrs of this._hwSources(this._hwEnt('hw_cost_daily','sensor.hello_watt_electricite_de_la_veille_abonnement_inclus'))){for(const j of attrs.jours||[]){if(j?.date?.startsWith(prefix))daily[j.date]={...(daily[j.date]||{}),...j};}}
 const map={},names=new Set();const unit=this._recapUnit==='kwh'?'kwh':'eur';
 for(const [date,j] of Object.entries(daily)){
 const values=j['tarifs_'+unit]||j['tempo_'+unit]||{},key=s.period==='y'?date.slice(0,7):date;const row=map[key]||(map[key]={});
 for(const [name,raw]of Object.entries(values)){const value=this._hwValue(raw);if(name==='subscription'||value==null||value<0)continue;names.add(name);row[name]=(row[name]||0)+value;}
 if(unit==='eur'&&this._hwValue(j.abonnement)!=null)row.subscription=(row.subscription||0)+Number(j.abonnement);
 const euros=j.tarifs_eur||j.tempo_eur||{},kwh=j.tarifs_kwh||j.tempo_kwh||{};
 }
 const known=new Map(this._hwTempoPalette().map(p=>[p[0],p]));
 const label=name=>this._cfg.tariff_labels?.[name]||(/^(base|standard)$/i.test(name)?'Base':/^(hp|heures?[-_ ]?pleines?|peak)$/i.test(name)?'Heures pleines':/^(hc|heures?[-_ ]?creuses?|off[-_ ]?peak)$/i.test(name)?'Heures creuses':name);
 let palette=[...names].sort().map((name,i)=>known.get(name)||[name,label(name),label(name)==='Heures creuses'?'#7dd3fc':label(name)==='Heures pleines'?'#2563eb':['#38bdf8','#a78bfa','#fb923c','#2dd4bf'][i%4]]);
 const onlyTempo=names.size>0&&[...names].every(k=>known.has(k));
 if(onlyTempo){palette=this._hwTempoDisplayPalette(s.period).filter(([key])=>s.period==='y'?[...names].some(k=>k.startsWith(key+'-')):names.has(key));if(s.period==='y')for(const row of Object.values(map))for(const color of ['red','white','blue'])row['Tempo-'+color]=(row['Tempo-'+color+'-HP']||0)+(row['Tempo-'+color+'-HC']||0);}
 else palette.sort((a,b)=>({'Heures pleines':0,'Heures creuses':1}[a[1]]??2)-({'Heures pleines':0,'Heures creuses':1}[b[1]]??2));
 const contract=onlyTempo?'Tempo':palette.length===1&&palette[0][1]==='Base'?'Base':palette.some(p=>p[1]==='Heures pleines')&&palette.some(p=>p[1]==='Heures creuses')?'Heures pleines / creuses':names.size?'Tarification détaillée':'Tarification non détaillée';
 return {map,palette:(unit==='eur'?[['subscription','Abonnement','#64748b']]:[]).concat(palette),contract};
}
_injectionState(s) {
 const original=this._recapUnit,c=this.cursor();const get=unit=>{this._recapUnit=unit;try{return s.period==='y'?this._hwYearSeries(c.y):this._hwSeries(c.y,c.m)}finally{this._recapUnit=original}};
 const energy=original==='kwh'?s:get('kwh'),money=original==='eur'?s:get('eur');const kwh=energy.monthInc,eur=money.monthInc;const requested=this._cfg.injection_mode||'auto';
 const mode=requested!=='auto'?requested:(eur>0?'paid':kwh>0&&eur===0?'free':kwh===0&&(eur===0||eur==null)?'none':'unknown');
 return {mode,kwh,eur,label:{paid:'Injection rémunérée',free:'Injection sans rémunération',none:'Sans injection',unknown:'Rémunération non renseignée'}[mode]};
}

_hwTempoPalette() {
    return [
      ["Tempo-red-HP", "Rouge HP", "#ef4444"], ["Tempo-red-HC", "Rouge HC", "#fda4af"],
      ["Tempo-white-HP", "Blanc HP", "#ffffff"], ["Tempo-white-HC", "Blanc HC", "#cbd5e1"],
      ["Tempo-blue-HP", "Bleu HP", "#2563eb"], ["Tempo-blue-HC", "Bleu HC", "#7dd3fc"]
    ];
  }
_hwTempoDisplayPalette(period) {
    return period === "y" ? [["Tempo-red", "Rouge", "#ef4444"], ["Tempo-white", "Blanc", "#ffffff"], ["Tempo-blue", "Bleu", "#2563eb"]] : this._hwTempoPalette();
  }
_hwTempoMap(s) {
    const kwh = this._recapUnit === "kwh", field = kwh ? "tempo_kwh" : "tempo_eur";
    const daily = {}, out = {};
    const prefix = String(s.y) + (s.period === "y" ? "-" : "-" + String(s.m+1).padStart(2,"0") + "-");
    this._hwSources(this._hwEnt("hw_cost_daily", "sensor.hello_watt_electricite_de_la_veille_abonnement_inclus")).forEach(a => {
      if (!Array.isArray(a.jours)) return;
      a.jours.forEach(j => {
        if (j && /^\d{4}-\d{2}-\d{2}$/.test(j.date) && j.date.startsWith(prefix) && j[field] && typeof j[field] === "object") daily[j.date] = j;
      });
    });
    const palette = this._hwTempoPalette();
    Object.entries(daily).forEach(([date,j]) => {
      const key = s.period === "y" ? date.slice(0,7) : date;
      const row = out[key] || (out[key] = {});
      palette.forEach(([tariff]) => {
        const value = this._hwValue(j[field][tariff]);
        if (value != null && value >= 0) row[tariff] = (row[tariff] || 0) + value;
      });
      if (!kwh && this._hwValue(j.abonnement) != null) row.subscription = (row.subscription || 0) + Number(j.abonnement);
    });
    return out;
  }
_hwKey(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
_hwValue(value) {
    if (value == null || typeof value === "boolean" || (typeof value === "string" && !value.trim())) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
_hwFieldKeys(field) {
    if (field === "production_kwh" || field === "production_eur") return [field];
    // Ne jamais convertir implicitement les euros en kWh.
    if (field === "consommation" || field === "consommation_kwh") return ["consommation_kwh"];
    if (field === "injection_kwh") return ["injection_kwh"];
    if (field === "electricite") return ["electricite", "cout"];
    return ["injection", "revenu"];
  }
_hwSources(entity) {
    const states = (this._hass && this._hass.states) || {};
    const energy = (this._cfg && this._cfg.energy) || {};
    const ids = new Set();
    const add = (id) => { if (typeof id === "string" && states[id]) ids.add(id); };
    // Les capteurs annuels peuvent aussi être explicitement associés par année.
    const configured = energy.hw_history_entities;
    if (Array.isArray(configured)) configured.forEach(add);
    else if (configured && typeof configured === "object") Object.values(configured).forEach(add);
    else add(configured);
    if (!configured) {
      Object.entries(states).forEach(([id, state]) => {
        const a = state.attributes || {};
        const name = String(a.friendly_name || "");
        if (/^sensor\.(?:hello_watt|hellowatt)_historique_\d{4}(?:_\d+)?$/.test(id)
            || (/hello\s*watt.*historique/i.test(name) && /^\d{4}$/.test(String(a.annee))
                && Array.isArray(a.jours) && Array.isArray(a.mois))) add(id);
      });
    }
    // Les capteurs usuels portent mois_historique et annees (mois est une chaîne).
    Object.keys(energy).filter(k => k.startsWith("hw_") && k !== "hw_history_entities").forEach(k => add(energy[k]));
    ["electricite_de_la_veille_abonnement_inclus", "revenu_injection_de_la_veille",
      "electricite_mensuelle_abonnement_inclus", "revenu_injection_mensuel",
      "electricite_annuelle_abonnement_inclus", "revenu_injection_annuel",
      "consommation_reseau_de_la_veille", "injection_reseau_de_la_veille",
      "consommation_reseau_mensuelle", "injection_reseau_mensuelle",
      "consommation_reseau_annuelle", "injection_reseau_annuelle"].forEach(n => add("sensor.hello_watt_" + n));
    // L'entité demandée conserve la priorité pour les données qu'elle possède.
    if (ids.has(entity)) ids.delete(entity);
    add(entity);
    return Array.from(ids, id => states[id].attributes || {});
  }
_hwMap(entity, field) {
    const out = {}, keys = this._hwFieldKeys(field);
    this._hwSources(entity).forEach(a => {
      if (!Array.isArray(a.jours)) return;
      a.jours.forEach(j => {
        if (!j || typeof j !== "object") return;
        const key = keys.find(k => this._hwValue(j[k]) != null);
        const day = /^(\d{4}-\d{2}-\d{2})(?:$|T)/.exec(String(j.date || ""));
        if (key && day) out[day[1]] = this._hwValue(j[key]);
      });
    });
    return out;
  }
_hwMonthMap(entity, field) {
    const out = {}, keys = this._hwFieldKeys(field);
    this._hwSources(entity).forEach(a => {
      [a.mois, a.mois_historique, a.months].filter(Array.isArray).forEach(rows => rows.forEach(j => {
        if (!j || typeof j !== "object") return;
        const key = keys.find(k => this._hwValue(j[k]) != null);
        const month = /^(\d{4}-\d{2})(?:$|-)/.exec(String(j.mois || j.date || j.month || ""));
        if (key && month) out[month[1]] = this._hwValue(j[key]);
      }));
    });
    return out;
  }
_hwMonthlyFromDays(entity, field) {
    const out = {}, daily = this._hwMap(entity, field);
    Object.keys(daily).forEach(k => { const month = k.slice(0, 7); out[month] = (out[month] || 0) + daily[k]; });
    return out;
  }
_hwPeriodTotal(entity, field, period) {
    const keys = this._hwFieldKeys(field);
    let result = null;
    const take = row => {
      const key = row && keys.find(k => this._hwValue(row[k]) != null);
      if (key) result = this._hwValue(row[key]);
    };
    this._hwSources(entity).forEach(a => {
      if (period.length === 4) {
        if (String(a.annee) === period && Array.isArray(a.mois)) take(a);
        if (Array.isArray(a.annees)) a.annees.forEach(row => { if (row && String(row.annee) === period) take(row); });
      } else {
        [a.mois, a.mois_historique, a.months].filter(Array.isArray).forEach(rows => rows.forEach(row => {
          if (row && String(row.mois || row.date || row.month || "").slice(0, 7) === period) take(row);
        }));
        if (a.mois === period) take(a);
      }
    });
    return result;
  }
_hwYearSeries(yArg) {
    const MO = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"];
    const now = new Date();
    const y = yArg == null ? now.getFullYear() : yArg;
    const kwh = this._recapUnit === "kwh";
    const costEnt = kwh ? this._hwEnt("hw_kwh_daily", "sensor.hello_watt_consommation_reseau_de_la_veille")
                        : this._hwEnt("hw_cost_daily", "sensor.hello_watt_electricite_de_la_veille_abonnement_inclus");
    const incEnt = kwh ? this._hwEnt("hw_kwh_income_daily", "sensor.hello_watt_injection_reseau_de_la_veille")
                       : this._hwEnt("hw_income_daily", "sensor.hello_watt_revenu_injection_de_la_veille");
    const costHist = kwh ? this._hwEnt("hw_kwh_monthly_history", "sensor.hello_watt_consommation_reseau_annuelle")
                         : this._hwEnt("hw_cost_monthly_history", "sensor.hello_watt_electricite_annuelle_abonnement_inclus");
    const incHist = kwh ? this._hwEnt("hw_kwh_income_monthly_history", "sensor.hello_watt_injection_reseau_annuelle")
                        : this._hwEnt("hw_income_monthly_history", "sensor.hello_watt_revenu_injection_annuel");
    const field = kwh ? "consommation_kwh" : "electricite";
    const incomeField = kwh ? "injection_kwh" : "injection";
    const cost = Object.assign(this._hwMonthlyFromDays(costEnt, field), this._hwMonthMap(costHist, field));
    const inc = Object.assign(this._hwMonthlyFromDays(incEnt, incomeField), this._hwMonthMap(incHist, incomeField));
    const liveMonth = y === now.getFullYear() ? this._hwSeries(y, now.getMonth()) : null;
    const days = [];
    for (let i = 0; i < 12; i++) {
      const key = y + "-" + String(i + 1).padStart(2, "0");
      const currentMonth = liveMonth && i === now.getMonth();
      const c = currentMonth ? liveMonth.monthCost : cost[key], v = currentMonth ? liveMonth.monthInc : inc[key];
      const current = y === now.getFullYear() && i === now.getMonth();
      days.push({ day: i + 1, label: MO[i], hi: true, jump: i, key,
        future: y === now.getFullYear() && i > now.getMonth(),
        cost: (c != null && Number.isFinite(Number(c))) ? Math.abs(c) : null, income: (v != null && Number.isFinite(Number(v))) ? Math.abs(v) : null,
        est: !!(currentMonth && liveMonth.estDay) });
    }
    const sum = (f) => days.reduce((a, x) => a + (f(x) || 0), 0);
    const avg = (f) => { const v = days.filter((d) => f(d) != null); return v.length ? v.reduce((a, d) => a + f(d), 0) / v.length : 0; };
    return { days, period: "y", y: y, m: null, isCurrent: y === now.getFullYear(),
      u: kwh ? "kWh" : "€", dec: kwh ? 0 : 2,
      title: kwh ? "Énergie mensuelle" : "Coût mensuel",
      statCost: kwh ? "Importé sur l'année" : "Coût de l'année",
      statInc: kwh ? "Injecté sur l'année" : "Revenu injection",
      statNet: kwh ? "Solde de l'année" : "Net de l'année",
      legCost: kwh ? "Énergie importée" : "Coût importé",
      legInc: kwh ? "Énergie injectée" : "Revenu injection",
      maxUp: Math.max(kwh ? 20 : 0.5, ...days.map((d) => d.cost || 0)),
      maxDown: Math.max(kwh ? 10 : 0.2, ...days.map((d) => d.income || 0)),
      sumCost: sum((d) => d.cost), sumInc: sum((d) => d.income),
      // cumuls affichés : capteurs annuels HelloWatt sur l'année en cours, sinon somme des mois
      monthCost: this._hwPeriodTotal(costHist, field, String(y)) != null ? this._hwPeriodTotal(costHist, field, String(y)) + (liveMonth?.estimatedCost || 0) : (days.some(d => d.cost != null) ? sum(d => d.cost) : null),
      monthInc: this._hwPeriodTotal(incHist, incomeField, String(y)) != null ? this._hwPeriodTotal(incHist, incomeField, String(y)) + (liveMonth?.estimatedIncome || 0) : (days.some(d => d.income != null) ? sum(d => d.income) : null),
      hasData: days.some((d) => d.cost != null || d.income != null),
      estDay: days.some((d) => d.est),
      attrKeys: (() => { const st0 = this._st(costHist || costEnt); return st0 ? Object.keys(st0.attributes || {}).slice(0, 12).join(", ") : "capteur introuvable"; })(),
      avgCost: avg((d) => d.cost), avgInc: avg((d) => d.income) };
  }
_hwSeries(yArg, mArg) {
    const kwh = this._recapUnit === "kwh";
    const costEnt = kwh ? this._hwEnt("hw_kwh_daily", "sensor.hello_watt_consommation_reseau_de_la_veille")
                        : this._hwEnt("hw_cost_daily", "sensor.hello_watt_electricite_de_la_veille_abonnement_inclus");
    const incEnt = kwh ? this._hwEnt("hw_kwh_income_daily", "sensor.hello_watt_injection_reseau_de_la_veille")
                       : this._hwEnt("hw_income_daily", "sensor.hello_watt_revenu_injection_de_la_veille");
    const cost = this._hwMap(costEnt, kwh ? "consommation_kwh" : "electricite");
    const inc = this._hwMap(incEnt, kwh ? "injection_kwh" : "injection");
    const now = new Date();
    const y = yArg == null ? now.getFullYear() : yArg;
    const m = mArg == null ? now.getMonth() : mArg;
    const isCurrent = y === now.getFullYear() && m === now.getMonth();
    const days = [];
    const nDays = new Date(y, m + 1, 0).getDate();
    for (let d = 1; d <= nDays; d++) {
      const key = this._hwKey(new Date(y, m, d));
      const c = cost[key], i = inc[key];
      days.push({ day: d, label: String(d), hi: d % 5 === 0 || d === 1 || d === nDays, key,
        future: isCurrent && d > now.getDate(), cost: (c != null && Number.isFinite(Number(c))) ? c : null, income: (i != null && Number.isFinite(Number(i))) ? Math.abs(i) : null });
    }
    const sum = (f) => days.reduce((a, x) => a + (f(x) || 0), 0);
    const periodKey = y + "-" + String(m + 1).padStart(2, "0");
    const monthCost = this._hwPeriodTotal(costEnt, kwh ? "consommation_kwh" : "electricite", periodKey);
    const monthInc = this._hwPeriodTotal(incEnt, kwh ? "injection_kwh" : "injection", periodKey);
    // Les capteurs "veille" s'arrêtent hier : le jour en cours est estimé depuis le
    // cumul mensuel (mensuel − somme des jours connus), à défaut le coût journalier.
    const today = isCurrent ? days[now.getDate() - 1] : null;
    if (today && today.cost == null) {
      const est = this._num(kwh ? this._hwEnt("today_kwh", "sensor.energie_importe_aujourd_hui_calibre")
                                : this._hwEnt("today_cost", "sensor.cout_energie_cout_energie_solaire_aujourdhui"), null);
      if (est != null && isFinite(est)) { today.cost = Math.abs(est); today.estimatedCost = today.cost; today.est = true; }
    }
    if (today && today.income == null) {
      const estI = this._num(kwh ? this._hwEnt("today_kwh_income", "sensor.vendu_daily")
                                 : this._hwEnt("today_income", "sensor.vendu_euro_daily"), null);
      if (estI != null && isFinite(estI)) { today.income = Math.abs(estI); today.estimatedIncome = today.income; today.est = true; }
    }
    return {
      days,
      period: "m", y: y, m: m, isCurrent: isCurrent,
      u: kwh ? "kWh" : "€", dec: kwh ? 1 : 2,
      title: kwh ? "Énergie quotidienne" : "Coût quotidien",
      statCost: kwh ? "Importé du mois" : "Coût du mois",
      statInc: kwh ? "Injecté du mois" : "Revenu injection",
      statNet: kwh ? "Solde du mois" : "Net du mois",
      legCost: kwh ? "Énergie importée" : "Coût importé",
      legInc: kwh ? "Énergie injectée" : "Revenu injection",
      maxUp: Math.max(kwh ? 2 : 0.5, ...days.map((d) => d.cost || 0)),
      maxDown: Math.max(kwh ? 1 : 0.2, ...days.map((d) => d.income || 0)),
      sumCost: sum((d) => d.cost),
      sumInc: sum((d) => d.income),
      estimatedCost: today?.estimatedCost || 0, estimatedIncome: today?.estimatedIncome || 0,
      monthCost: monthCost != null ? monthCost + (today?.estimatedCost || 0) : (days.some(d => d.cost != null) ? sum(d => d.cost) : null),
      monthInc: monthInc != null ? monthInc + (today?.estimatedIncome || 0) : (days.some(d => d.income != null) ? sum(d => d.income) : null),
      hasData: days.some((d) => d.cost != null || d.income != null),
      estDay: !!(today && today.est),
    attrKeys: (() => {
      const st0 = this._st(this._hwEnt("hw_cost_daily", "sensor.hello_watt_electricite_de_la_veille_abonnement_inclus"));
      return st0 ? Object.keys(st0.attributes || {}).slice(0, 12).join(", ") : "capteur introuvable";
    })(),
    avgCost: (() => { const v = days.filter((d) => d.cost != null); return v.length ? v.reduce((a, d) => a + d.cost, 0) / v.length : 0; })(),
    avgInc: (() => { const v = days.filter((d) => d.income != null); return v.length ? v.reduce((a, d) => a + d.income, 0) / v.length : 0; })(),
    };
  }}
const CSS=`.average.avg-export{border-color:var(--pink)}.mean-legend{display:flex;gap:10px 20px;flex-wrap:wrap;margin-top:10px;font-size:10px;color:var(--blue)}.mean-legend span::before{content:"";display:inline-block;width:18px;border-top:1px dashed currentColor;vertical-align:middle;margin-right:6px}.mean-legend span+span{color:var(--pink)}.context{display:flex;gap:8px;flex-wrap:wrap;margin:-8px 0 18px}.context span{font-size:10px;color:var(--muted);padding:5px 9px;border:1px solid var(--line);border-radius:20px}.no-export .down{display:none}.no-export .chart{height:199px}.no-export .gridlines{bottom:29px}:host{display:block;container-type:inline-size}*{box-sizing:border-box}ha-card{--blue:#38bdf8;--pink:#ec4899;--fg:#f4f6fa;--muted:#94a0b2;--line:#ffffff13;--panel:#ffffff04;display:block;padding:24px;border-radius:24px;color:var(--fg);background:radial-gradient(ellipse at 0 0,#14303b77,transparent 55%),#0d1117;border:1px solid var(--line);font-family:var(--primary-font-family,Inter,Arial,sans-serif);box-shadow:0 12px 40px #0002}ha-card.light{--blue:#087bab;--pink:#c02678;--fg:#172235;--muted:#64748b;--line:#162b4720;--panel:#ffffffbb;background:radial-gradient(ellipse at 0 0,#dff4ff,transparent 65%),#f7f9fc}button{font:inherit;color:inherit;cursor:pointer;border:1px solid var(--line);background:var(--panel)}button:focus-visible{outline:2px solid var(--blue);outline-offset:3px}button:disabled{opacity:.3;cursor:default}header,.subhead,.controls,.navigate,.heading{display:flex;align-items:center}header,.subhead{justify-content:space-between;gap:16px}.heading{gap:12px}.icon{width:42px;height:42px;border-radius:14px;background:#38bdf820;display:grid;place-items:center;color:var(--blue);font-size:30px}.eyebrow{font-size:9px;letter-spacing:.2em;color:var(--muted);margin-bottom:5px}h2{font-size:23px;letter-spacing:-.04em;margin:0;font-weight:600}.controls{gap:10px}.switch{display:flex;padding:3px;gap:3px;border-radius:13px;border:1px solid var(--line);background:var(--panel)}.chip{border:0;border-radius:9px;padding:8px 12px;font-size:12px;color:var(--muted);background:transparent}.chip.active{background:#38bdf820;color:var(--fg);box-shadow:inset 0 0 0 1px #38bdf835}.subhead{margin:16px 0 22px}.subhead p{font-size:12px;color:var(--muted);margin:0}.navigate{gap:12px}.navigate button{width:30px;height:30px;border-radius:10px;font-size:24px;line-height:1}.navigate strong{font-size:13px;font-weight:500;text-transform:capitalize;min-width:115px;text-align:center}.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:20px}.stat{padding:18px 20px;border:1px solid var(--line);border-radius:18px;background:linear-gradient(130deg,var(--panel),transparent)}.stat>span{color:var(--muted);font-size:10px;letter-spacing:.07em;text-transform:uppercase}.stat>div{font-size:34px;letter-spacing:-.04em;font-weight:600;margin-top:12px;font-variant-numeric:tabular-nums}.stat small{color:var(--muted);font-size:15px;letter-spacing:0;font-weight:400}.cost>div{color:var(--blue)}.income>div{color:var(--pink)}.graph{padding:20px 18px 12px;border:1px solid var(--line);border-radius:20px;background:var(--panel)}.legend{display:flex;flex-wrap:wrap;gap:10px 20px;font-size:12px;color:var(--muted)}.legend span{display:inline-flex;gap:7px;align-items:center}.legend i{height:9px;width:9px;border-radius:3px;box-shadow:inset 0 0 0 1px #0002}.tempo{margin-top:14px;gap:8px 14px;font-size:10px}.chart-scroll{overflow-x:auto;margin-top:22px;padding-bottom:5px}.chart{display:flex;min-width:550px;height:243px;gap:12px}.axis{width:62px;flex:none;position:relative;color:var(--muted);font-size:10px;text-align:right}.axis span{position:absolute;right:0;top:0}.axis span:nth-child(2){top:164px}.axis span:nth-child(3){top:208px}.plot{flex:1;min-width:0;position:relative}.bars{display:flex;gap:4px;position:relative;z-index:1}.day{display:flex;flex:1;min-width:0;flex-direction:column;padding:0;border:0;border-radius:0;background:none}.up,.down{width:100%;display:flex;justify-content:center}.up{height:170px;align-items:flex-end}.down{height:44px;align-items:flex-start}.stack,.export{width:76%;max-width:32px;display:flex}.stack{flex-direction:column-reverse;border-radius:5px 5px 0 0;overflow:hidden;background:var(--blue)}.stack i{display:block;min-height:0}.export{background:linear-gradient(var(--pink),#ec489980);border-radius:0 0 5px 5px}.label{color:var(--muted);font-size:10px;margin:9px auto 0}.future .label{opacity:.4}.day:hover,.day.selected{background:#38bdf80c}.day.selected .label{color:var(--blue)}.gridlines{position:absolute;inset:0 0 29px;pointer-events:none}.gridlines i{position:absolute;left:0;right:0;border-top:1px solid var(--line);top:0}.gridlines i:nth-child(2){top:85px}.gridlines i:nth-child(3){top:170px;border-top-width:2px}.average{position:absolute;left:0;right:0;border-top:1px dashed var(--blue);opacity:.45;pointer-events:none}.estimated{background:repeating-linear-gradient(135deg,var(--blue) 0 3px,transparent 3px 7px)}.export.estimated{background:repeating-linear-gradient(135deg,var(--pink) 0 3px,transparent 3px 7px)}footer{border-top:1px solid var(--line);margin-top:14px;padding-top:12px;display:flex;justify-content:space-between;gap:12px;color:var(--muted);font-size:10px;line-height:1.5}.empty{text-align:center;padding:55px 15px;color:var(--muted);font-size:14px}.empty small{display:block;margin-top:12px;font-size:11px}@container(max-width:650px){ha-card{padding:16px;border-radius:18px}header{align-items:flex-start;flex-wrap:wrap}h2{font-size:20px}.controls{width:100%;justify-content:space-between}.subhead{align-items:flex-start;flex-direction:column;gap:12px}.navigate{width:100%;justify-content:space-between}.stats{gap:7px}.stat{padding:12px 9px;border-radius:13px}.stat>span{font-size:8px;letter-spacing:0}.stat>div{font-size:clamp(19px,6cqw,30px);margin-top:10px;white-space:nowrap}.stat small{font-size:11px}.graph{padding:15px 10px}footer{flex-wrap:wrap}.legend{font-size:11px}.tempo{font-size:9px}}`;
customElements.define('hello-watt-cost-card',HelloWattCostCard);
window.customCards=window.customCards||[];if(!window.customCards.some(c=>c.type==='hello-watt-cost-card'))window.customCards.push({type:'hello-watt-cost-card',name:'Hello Watt — Coût quotidien',description:'Import, injection et bilan en € ou kWh, avec historique et Tempo.',preview:true});
})();
