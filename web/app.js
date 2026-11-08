const $=s=>document.querySelector(s);
const S={w:0,view:'dashboard',edit:false,d:null,role:'',staffName:'',dev:false};
const canEditCalendar=()=>['admin','coordinator'].includes(S.role);
const PX=60,T0=480,T1=1080,SNAP=15,DAYS=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const dayN=i=>new Date(Date.UTC(2026,10,9+i)),iso=d=>d.toISOString().slice(0,10);
const F=(d,o)=>d.toLocaleDateString('en-GB',{timeZone:'UTC',...o});
const mins=t=>t?+t.slice(0,2)*60+ +t.slice(3,5):null;
const hhmm=m=>String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0');
const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function range(w){const a=dayN(w*7),b=dayN(w*7+6),Y=b.getUTCFullYear(),A=a.getUTCMonth(),B=b.getUTCMonth();return A==B?`${a.getUTCDate()}–${b.getUTCDate()} ${MON[B]} ${Y}`:`${a.getUTCDate()} ${MON[A]}–${b.getUTCDate()} ${MON[B]} ${Y}`}
const wkName=w=>S.d.settings['wk'+w]||`Week ${11+w}`;
const mod=id=>S.d.modules.find(m=>m.id==id),fac=id=>S.d.facilitators.find(f=>f.id==id);
const hex=h=>h.length==4?'#'+[...h.slice(1)].map(c=>c+c).join(''):h;
const mixc=(a,b,t)=>{a=hex(a);b=hex(b);return '#'+[1,3,5].map(i=>Math.round(parseInt(a.slice(i,i+2),16)*(1-t)+parseInt(b.slice(i,i+2),16)*t).toString(16).padStart(2,'0')).join('')};
const lum=h=>{h=hex(h);const[r,g,b]=[1,3,5].map(i=>{const c=parseInt(h.slice(i,i+2),16)/255;return c<=.03928?c/12.92:((c+.055)/1.055)**2.4});return .2126*r+.7152*g+.0722*b};
const inkFor=h=>lum(h)>.179?'#16191f':'#f3eee2';
const V=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const THEMES=[{id:'night',name:'Midnight Dark (default)',bg:'#0f1a2e',head:'#26406b',side:'#0a1222'},{id:'clear',name:'Clear White',bg:'#f4f6f9',head:'#1f4e79',side:'#14213d'},{id:'pure',name:'Pure White',bg:'#ffffff',head:'#0f5c6e',side:'#14213d'},
 {id:'mint',name:'Soft Mint',bg:'#e8f5ee',head:'#1b6b4a',side:'#12332a'},{id:'sky',name:'Sky Blue',bg:'#e6f1fb',head:'#1d4f91',side:'#11284a'},
 {id:'lav',name:'Lavender',bg:'#efeafa',head:'#5a3d99',side:'#271a45'},{id:'sand',name:'Warm Sand',bg:'#f5efe3',head:'#8a4b14',side:'#3a2a16'},
 {id:'slate',name:'Slate (dark)',bg:'#1e2430',head:'#2a6a8c',side:'#0f131a'},{id:'custom',name:'Custom background',bg:'#f4f6f9',head:'',side:'#14213d'}];
const curTheme=()=>{try{return localStorage.theme||'night'}catch(_){return 'night'}};
function applyTheme(){const t=THEMES.find(x=>x.id==curTheme())||THEMES[0],bg=t.id=='custom'?(localStorage.bgc||t.bg):t.bg,dark=lum(bg)<.179,
 card=dark?mixc(bg,'#ffffff',.07):mixc(bg,'#ffffff',.85),head=t.head||(dark?'#2a6a8c':'#1f4e79'),ink=inkFor(card),R=document.documentElement.style;
 const set={'--bg':bg,'--card':card,'--card2':dark?mixc(bg,'#000000',.2):mixc(card,'#000000',.04),'--ink':ink,'--line':dark?mixc(bg,'#ffffff',.2):mixc(bg,'#000000',.15),
 '--muted':mixc(ink,card,.3),'--head':head,'--headink':inkFor(head),'--side':t.side,'--accent':dark?'#d4a640':'#9a6f12','--danger':dark?'#ff8a80':'#b3261e','color-scheme':dark?'dark':'light'};for(const k in set)R.setProperty(k,set[k])}
function setTheme(id){localStorage.theme=id;applyTheme();if($('#theme'))$('#theme').value=id;if(S.d)render()}
const TYPES=[{id:'module',name:'Module session',color:'#2e7d4f'},{id:'journal',name:'Weekly Journal Club',color:'#b5530a'},{id:'conference',name:'Weekly Maternal Conference',color:'#7b3fa0'},
 {id:'exam',name:'Examination',color:'#b3261e'},{id:'recurring',name:'Recurring Activity',color:'#5f6b7a'},{id:'other',name:'Other session',color:'#0b6e8f'}];
const typeOf=e=>TYPES.find(t=>t.id==(e.stype||(e.kind=='exam'?'exam':e.kind=='recurring'?'recurring':e.module_id?'module':'other')))||TYPES[5];
const typeColor=t=>S.d?.settings['tc_'+t.id]||t.color,color=e=>typeColor(typeOf(e));
const TODAY=()=>new Date().toLocaleDateString('en-CA');
const legendHTML=()=>`<div class="legend">${TYPES.map(t=>`<span><i class="sw" style="background:${typeColor(t)}"></i>${esc(t.name)}</span>`).join('')}</div>`;
const TITLES=new Set('dr prof professor mr mrs ms miss mx rev reverend sir dame hon honourable honorable eng engr pastor fr br chief lord lady madam mister'.split(' ')),SUFFIX=new Set('jr sr phd md msc mph dphil esq'.split(' '));
const Ident={parts(n){let t=String(n||'').replace(/[.,()]/g,' ').split(/\s+/).filter(Boolean);while(t.length>1&&TITLES.has(t[0].toLowerCase()))t.shift();while(t.length>1&&SUFFIX.has(t[t.length-1].toLowerCase()))t.pop();return t},
 initials(n){const t=this.parts(n);if(!t.length||(t.length==1&&TITLES.has(t[0].toLowerCase())))return'?';return (Array.from(t[0])[0]+(t.length>1?Array.from(t[t.length-1])[0]:'')).toUpperCase()}};
const ini=n=>Ident.initials(n);
const av=(f,s=22)=>!f?'':f.avatar?`<img class="av" data-fac="${f.id}" style="width:${s}px;height:${s}px" src="/uploads/${f.avatar}">`:
 `<span class="av ini" data-fac="${f.id}" style="width:${s}px;height:${s}px;font-size:${s*.4}px">${esc(ini(f.name||'?'))}</span>`;
const me=()=>{let n=localStorage.editor;if(!n){n=(prompt('Enter your name (recorded as the editor in Activity History):')||'').trim();if(n)localStorage.editor=n}return n};
async function api(p,m='GET',b){const token=sessionStorage.ctoken||'';const headers={'Content-Type':'application/json'};if(token)headers.Authorization='Bearer '+token;
 const r=await fetch('/api/'+p,{method:m,headers,body:b?JSON.stringify(b):undefined}).catch(()=>{throw new Error('Cannot reach the server. Check that the backend is running.')});
 const t=await r.text();let j={};try{j=JSON.parse(t)}catch(_){}if(!r.ok)throw new Error(j.detail||t||('Request failed ('+r.status+')'));return j}
function showCalendarLogin(message='Sign in with your staff access token to open the academic calendar.'){document.body.classList.remove('so');$('#nav').innerHTML='';$('#me').textContent='';$('#ttl').textContent='Staff sign in';$('#mode').textContent='';$('#view').innerHTML=`<div class="card" style="max-width:480px;margin:8vh auto;padding:28px"><h2>PhD MNH Academic Calendar</h2><p>${esc(message)}</p><label>Staff access token<input id="calendarToken" type="password" autocomplete="current-password" placeholder="Paste administrator or staff token"></label><div class="row"><button class="btn pri" id="calendarSignIn">Sign in</button></div><small>First-run administrator token: backend/data/ADMIN_TOKEN.txt</small></div>`;$('#calendarSignIn').onclick=async()=>{sessionStorage.ctoken=$('#calendarToken').value.trim();try{await load()}catch(e){sessionStorage.removeItem('ctoken');showCalendarLogin(e.message)}}}
async function load(){
 try{const who=await api('comms/whoami');S.role=who.role;S.staffName=who.name;S.dev=!!who.dev;S.d=await api('bootstrap');render()}
 catch(e){const m=String(e&&e.message||e);if(/\b401\b|not signed in|sign in with/i.test(m)){sessionStorage.removeItem('ctoken');showCalendarLogin(m)}else showLoadError(m)}}
function showLoadError(message){S.dev=false;document.body.classList.remove('so');$('#nav').innerHTML='';$('#me').textContent='';$('#ttl').textContent='Calendar could not load';$('#mode').textContent='';$('#view').innerHTML=`<div class="card" style="max-width:480px;margin:8vh auto;padding:28px"><h2>Calendar could not load</h2><p>${esc(message)}</p><div class="row"><button class="btn pri" id="retryLoad">Retry</button></div><small>Check that the backend is running and reachable.</small></div>`;$('#retryLoad').onclick=()=>load()}
function conflicts(e){return S.d.events.filter(o=>o.id!=e.id&&o.date==e.date&&(()=>{const a=mins(e.start),b=mins(o.start);
 return a==null||b==null||(a<mins(o.end)&&b<mins(e.end))})())}
const inWeek=w=>S.d.events.filter(e=>e.date>=iso(dayN(w*7))&&e.date<=iso(dayN(w*7+6)));
const NAV=[['dashboard','Dashboard'],['weekly','Weekly Calendar'],['monthly','Monthly Calendar'],['modules','Modules'],['facilitators','Facilitators'],['exams','Examinations'],['recur','Recurring Activities'],['comms','WhatsApp & Communications'],['editor','Editor'],['histV','Activity History'],['export','Export and Sharing'],['settings','Settings']];
const navItems=()=>{let a=NAV.filter(([k])=>canEditCalendar()||k!='editor');if(['student','class_rep'].includes(S.role))a=a.filter(([k])=>k!='export');return a};
const SIDE=()=>{const o=[];navItems().forEach(([k,n])=>{o.push({k,n});if(k=='weekly')for(let i=0;i<NWK();i++)o.push({w:i})});return o};
const NWK=()=>6;
function chrome(){
 $('#nav').innerHTML=SIDE().map(it=>it.w!=null?`<button class="wk ${it.w==S.w?'on':''}" data-w="${it.w}" title="${esc(wkName(it.w))}: ${range(it.w)}"><b>${esc(wkName(it.w))}</b><span>${range(it.w)}</span></button>`:`<button data-v="${it.k}" class="${it.k==S.view?'on':''}">${it.n}</button>`).join('');
 $('#me').innerHTML=meChip();
 $('#ttl').textContent=({dashboard:S.d.settings.title,weekly:wkName(S.w)+' · '+range(S.w)}[S.view])||navItems().find(n=>n[0]==S.view)?.[1]||'Academic Calendar';
 $('#mode').textContent=[S.edit?'Editor ON':'',S.dev?'Dev mode – no sign-in':''].filter(Boolean).join(' · ');}
function render(){if(S.view=='editor'&&!canEditCalendar())S.view='dashboard';document.body.classList.remove('so');chrome();$('#view').innerHTML=({dashboard,weekly:()=>weeklyHTML(),monthly,modules,facilitators,editor,histV,exportV,settings,exams:examsV,recur:recurV,comms:commsV,history:histV})[S.view==='history'?'histV':S.view]();}
/* ---------- weekly grid ---------- */
const pos=e=>{const a=Math.max(mins(e.start),T0),b=Math.min(mins(e.end),T1);return b>a?{top:(a-T0)*PX/60,h:(b-a)*PX/60}:null};
function lanes(evs){const s=[...evs].sort((a,b)=>mins(a.start)-mins(b.start)||mins(b.end)-mins(a.end)),out=[];let g=[],end=0;
 const fl=()=>{const L=[];g.forEach(e=>{let i=L.findIndex(x=>x<=mins(e.start));if(i<0){i=L.length;L.push(0)}L[i]=mins(e.end);e._l=i});g.forEach(e=>e._n=L.length);out.push(...g);g=[]};
 s.forEach(e=>{if(g.length&&mins(e.start)>=end){fl();end=0}g.push(e);end=Math.max(end,mins(e.end))});if(g.length)fl();return out}
const stOf=e=>e.status=='cancelled'?'cancelled':(new Date(`${e.date}T${e.end||'23:59'}:00`)<new Date()?'completed':'upcoming');
function evHTML(e){const p=pos(e);if(!p)return'';const f=fac(e.facilitator_id),m=mod(e.module_id),c=conflicts(e).length,w=100/e._n;
 return `<div class="ev k-${e.kind} ${e.status=='cancelled'?'cx':''}" data-id="${e.id}" style="top:${p.top}px;height:${p.h}px;left:calc(${e._l*w}% + 2px);width:calc(${w}% - 4px);background:${color(e)};color:${inkFor(color(e))};border-left:5px solid ${m?m.color:'rgba(0,0,0,.3)'}"><b>${c?'⚠ ':''}${esc(e.title)}</b>${e.start}–${e.end}${m?' · '+esc(m.code):''}${f?'<br>'+av(f,16)+esc(f.name):''}${e.venue?'<br>'+esc(e.venue):''}<div class="rs"></div></div>`}
function weeklyHTML(){const evs=inWeek(S.w);let h='<div class="cal"><div></div>';
 for(let i=0;i<7;i++){const d=dayN(S.w*7+i);h+=`<div class="hd ${iso(d)==TODAY()?'today':''}">${DAYS[i]}<small>${F(d,{day:'numeric',month:'short'})}</small></div>`}
 h+='<div class="un"></div>';
 for(let i=0;i<7;i++)h+=`<div class="un">${evs.filter(e=>e.date==iso(dayN(S.w*7+i))&&!e.start).map(e=>`<span class="chip" data-id="${e.id}" style="background:${color(e)};color:${inkFor(color(e))}">⚠ ${esc(e.title)} (time not confirmed)</span>`).join('')}</div>`;
 h+='<div class="tl">'+[...Array((T1-T0)/60+1)].map((_,i)=>`<span style="top:${i*PX}px">${hhmm(T0+i*60)}</span>`).join('')+'</div>';
 for(let i=0;i<7;i++){const ds=iso(dayN(S.w*7+i));h+=`<div class="col ${i>4?'we':''}" data-date="${ds}">${lanes(evs.filter(e=>e.date==ds&&e.start)).map(evHTML).join('')}</div>`}
 return h+'</div>'+legendHTML()+'<p style="color:var(--muted);font-size:12px">Each row is one hour; sessions keep their exact start/end. Click an empty slot to create · drag to move · drag the bottom edge to resize · ⚠ marks conflicts.</p>'}
const upcoming=()=>S.d.events.filter(e=>stOf(e)=='upcoming').sort((a,b)=>(a.date+(a.start||'')).localeCompare(b.date+(b.start||'')));
const dT=e=>`${F(new Date(e.date),{weekday:'short',day:'numeric',month:'short',timeZone:'UTC'})}${e.start?' '+e.start+'–'+e.end:''}`;
function dashData(w){const ev=inWeek(w),c={completed:0,upcoming:0,cancelled:0};ev.forEach(e=>c[stOf(e)]++);
 const fs=[...new Set(ev.map(e=>e.facilitator_id).filter(Boolean))].map(fac).filter(Boolean);
 return{ev,c,fs,
 week:[wkName(w),range(w),'Block Three · 9 Nov – 20 Dec 2026'],
 sess:[`${ev.length} session${ev.length==1?'':'s'}`,`${c.completed} completed · ${c.upcoming} upcoming · ${c.cancelled} cancelled`],
 exams:S.d.events.filter(e=>e.kind=='exam').map(e=>`${dT(e)} · ${mod(e.module_id)?.code||''} ${e.title} — ${e.start?'time confirmed':'time not confirmed'}`),
 rec:ev.filter(e=>e.kind=='recurring').map(e=>`${dT(e)} · ${e.title}`),
 facs:fs.map(f=>`${f.name}: ${ev.filter(e=>e.facilitator_id==f.id).map(e=>e.title).join('; ')}`),
 up:upcoming().slice(0,6).map(e=>`${dT(e)} · ${e.title}`)}}
function dashboard(){const d=dashData(S.w),L=a=>`<div class="lines">${(a.length?a:['None']).map(x=>`<div>${esc(x)}</div>`).join('')}</div>`,C=(go,t,b,x='')=>`<div class="card go ${x}" data-go="${go}"><h4>${t}</h4>${b}</div>`;
 return '<div class="stats">'+C('weekly','Current academic week',`<b>${esc(d.week[0])}</b><div>${d.week[1]}</div><small>${d.week[2]}</small>`)+C('weekly','Sessions this week',`<b style="font-size:20px">${d.ev.length}</b><br><small>${d.sess[1]}</small>`)
 +C('exams','Upcoming examinations',L(d.exams))+C('recur','Recurring activities',L(d.rec))
 +C('facilitators','Facilitators',d.fs.length?`<div class="lines">${d.fs.map(f=>`<div>${av(f)}${esc(f.name)}<br><small>${esc(d.ev.filter(e=>e.facilitator_id==f.id).map(e=>e.title).join('; '))}</small></div>`).join('')}</div>`:L([]))
 +C('monthly','Upcoming academic activities',L(d.up),'wide')+'</div>'+weeklyHTML()}
const weekly=weeklyHTML;
function monthly(){let h='<div class="month">'+DAYS.map(d=>`<div class="hd">${d}</div>`).join('');
 for(let i=0;i<Math.max(42,NWK()*7);i++){const d=dayN(i),ds=iso(d),es=S.d.events.filter(e=>e.date==ds).sort((a,b)=>(a.start||'')<(b.start||'')?-1:1);
  h+=`<div class="mc "><b>${F(d,{day:'numeric',month:'short'})}</b>${es.map(e=>`<span class="chip" data-id="${e.id}" style="background:${color(e)};color:${inkFor(color(e))}">${e.start||'⚠'} ${esc(e.title)}</span>`).join('')}</div>`}
 return h+'</div>'}
/* ---------- other views ---------- */
function examsV(){const ex=S.d.events.filter(e=>e.kind=='exam').sort((a,b)=>a.date.localeCompare(b.date));
 return `${canEditCalendar()?'<p><button class="btn pri" data-newex>+ Add examination</button></p>':''}<table><tr><th>Date</th><th>Examination</th><th>Module</th><th>Time</th><th></th></tr>`+ex.map(e=>`<tr><td>${e.date}</td><td>${esc(e.title)}</td><td>${esc(mod(e.module_id)?.code||'')}</td><td>${e.start?e.start+'–'+e.end:'<b>Not confirmed</b>'}</td><td>${canEditCalendar()?`<button class="btn" data-ed="${e.id}">Edit</button>`:''}</td></tr>`).join('')+'</table>'}
function recurV(){const g={};S.d.events.filter(e=>e.series_id).forEach(e=>(g[e.series_id]??=[]).push(e));
 return `<table><tr><th>Day</th><th>Time</th><th>Activity</th><th>Occurrences</th><th></th></tr>`+Object.values(g).map(a=>{a.sort((x,y)=>x.date.localeCompare(y.date));const e=a[0];return `<tr><td>${F(new Date(e.date),{weekday:'long',timeZone:'UTC'})}</td><td>${e.start}–${e.end}</td><td>${esc(e.title)}</td><td>${a.length}</td><td>${canEditCalendar()?`<button class="btn" data-ed="${e.id}" data-sc="series">Edit series</button>`:''}</td></tr>`}).join('')+'</table>'}
function modules(){return `<table><tr><th>Colour</th><th>Code</th><th>Module</th><th>Facilitators</th><th></th></tr>`+S.d.modules.map(m=>`<tr><td><span class="sw" style="background:${m.color}"></span></td><td>${esc(m.code)}</td><td>${esc(m.name)}</td>
 <td>${S.d.facilitators.filter(f=>f.module_id==m.id).map(f=>av(f)+esc(f.name)).join('<br>')}</td><td>${canEditCalendar()?`<button class="btn" data-mod="${m.id}">Edit</button>`:''}</td></tr>`).join('')+'</table>'}
function facilitators(){return `${canEditCalendar()?'<p><button class="btn pri" data-fac-new>+ Add facilitator</button></p>':''}<div class="grid">`+S.d.facilitators.map(f=>`<div class="card">${av(f,48)}<b>${esc(f.name)}</b><br>${esc(f.designation)}<br><small>${esc(mod(f.module_id)?.code||'')}</small>${canEditCalendar()?`<div class="row"><button class="btn" data-fac-edit="${f.id}">Edit profile</button></div>`:''}</div>`).join('')+'</div>'||''}
function editor(){return `<div class="card" style="max-width:640px"><h4>Universal editor</h4><p>Editor mode lets you click any session, the programme title, or a week label and change it immediately. Every saved change is recorded with its previous and new value.</p>
 <div class="row"><button class="btn pri" id="tgl">${S.edit?'Turn Editor mode OFF':'Turn Editor mode ON'}</button><button class="btn" onclick="act('undo')">Undo</button><button class="btn" onclick="act('redo')">Redo</button></div>
 <p style="font-size:12px">${S.edit?'Click the programme title (Settings) or a week in the sidebar with Shift to rename it; click any event to edit.':''}</p></div>`}
function histV(){return `<table><tr><th>When</th><th>By</th><th>Item</th><th>Field</th><th>Previous</th><th>New</th><th></th></tr>`+S.d.history.map(h=>`<tr style="${h.undone?'opacity:.5':''}"><td>${h.ts.replace('T',' ')}</td><td>${esc(h.user)}</td><td>${esc(h.label)}</td><td>${esc(h.field)}</td><td>${esc(h.old)}</td><td>${esc(h.new)}</td><td>${canEditCalendar()?`<button class="btn" data-restore="${h.id}">Restore previous</button>`:''}</td></tr>`).join('')+'</table>'}
function exportV(){return `<div class="card" style="max-width:560px"><h4>Export selected week (${esc(wkName(S.w))})</h4><div class="row">
 <button class="btn" data-x="pdf">PDF</button><button class="btn" data-x="docx">DOCX</button><button class="btn" data-x="png">PNG</button><button class="btn" onclick="print()">Print layout</button></div>
 <h4 style="margin-top:14px">Share and backup</h4><div class="row"><button class="btn" data-ics>Shareable calendar (.ics)</button><button class="btn" data-backup>JSON backup</button><label class="btn">Restore JSON<input type="file" id="rst" accept=".json" hidden></label></div></div>`}
function settings(){const o=THEMES.map(t=>`<option value="${t.id}" ${t.id==curTheme()?'selected':''}>${t.name}</option>`).join('');
 return `<div class="card" style="max-width:540px"><h4>Theme</h4><select id="themeS">${o}</select><div style="margin-top:8px"><label>Custom background <input type="color" id="cbg" value="${localStorage.bgc||'#f4f6f9'}" style="width:60px"></label></div><small>Text, grid lines, cards and headers adjust automatically for contrast.</small>
 <h4 style="margin-top:14px">Session type colours</h4>${TYPES.map(t=>`<div style="margin:4px 0"><input type="color" class="tcol" data-t="${t.id}" value="${typeColor(t)}"> ${esc(t.name)}</div>`).join('')}
 <h4 style="margin-top:14px">Local display profile</h4><small>This display name is stored only in this browser. Activity History uses your authenticated staff account.</small><div class="avrow">${localStorage.editorAv?`<img class="av" style="width:56px;height:56px" src="${localStorage.editorAv}" alt="">`:`<span class="av ini" style="width:56px;height:56px;font-size:20px">${esc(ini(localStorage.editor||'?'))}</span>`}<button class="btn" onclick="meAvatar()">${localStorage.editorAv?'Change':'Add'} photo</button></div><input id="ed" value="${esc(localStorage.editor||'')}" placeholder="Your name"><h4 style="margin-top:12px">Programme title</h4><input id="pt" value="${esc(S.d.settings.title)}">
 <div class="row">${canEditCalendar()?'<button class="btn pri" id="sv">Save</button>':''}<button class="btn" id="calendarSignOut">Sign out</button></div></div>`}
/* ---------- drawer ---------- */
let DIRTY=false;
const dr=h=>{const d=$('#drawer');d.innerHTML=h?`<button class="x" aria-label="Close panel" title="Close (Esc)" onclick="closeDrawer()">✕</button>`+h:'';d.hidden=!h;d.setAttribute('role','dialog');DIRTY=false;if(h)setTimeout(()=>d.querySelector('input,select,textarea,button:not(.x)')?.focus(),30)};
const closeDrawer=()=>{if(DIRTY&&!confirm('Discard unsaved changes?'))return;dr('')};
function details(id){const e=S.d.events.find(x=>x.id==id),f=fac(e.facilitator_id),m=mod(e.module_id),cf=conflicts(e);
 dr(`<h3>${esc(e.title)}</h3><p>${e.start?`${e.date} · ${e.start}–${e.end}`:`${e.date} · <b>time not confirmed</b>`}</p><p>${m?`<span class="sw" style="background:${m.color}"></span>${esc(m.code)} – ${esc(m.name)}`:'No module assigned'}</p>
 <p>${f?av(f,28)+esc(f.name):'No facilitator assigned'}</p><p>Venue: ${esc(e.venue)||'—'}</p><p>${esc(e.description)}</p>
 ${cf.length?`<div class="warn">⚠ Conflict with: ${cf.map(c=>esc(c.title)).join('; ')}${!e.start?'<br>Examination time is unconfirmed – please confirm the time.':''}</div>`:''}
 <div class="row">${canEditCalendar()?`<button class="btn pri" onclick="form(${id})">Edit</button>`:''}<button class="btn" onclick="closeDrawer()">Close</button></div>`)}
function opts(list,sel,l){return '<option value="">—</option>'+list.map(x=>`<option value="${x.id}" ${x.id==sel?'selected':''}>${esc(l(x))}</option>`).join('')}
let NEWK='session';
function form(id,pre={}){const e=id?S.d.events.find(x=>x.id==id):{title:'',date:pre.date,start:pre.start,end:pre.end,kind:pre.kind||'session'},ser=e.series_id,sr=pre.scope=='series';NEWK=e.kind;
 dr(`<h3>${id?'Edit':'New'} ${e.kind=='exam'?'examination':'session'}</h3><label>Title<input id="f_title" value="${esc(e.title)}"></label>
 <label>Module<select id="f_module_id">${opts(S.d.modules,e.module_id,m=>m.code+' – '+m.name)}</select></label>
 <label>Facilitator<select id="f_facilitator_id">${opts(S.d.facilitators,e.facilitator_id,f=>f.name)}</select></label>
 <label>Date<input type="date" id="f_date" min="2026-11-09" max="2026-12-20" value="${e.date||''}"></label>
 <label>Start<input type="time" id="f_start" step="300" value="${e.start||''}"></label><label>End<input type="time" id="f_end" step="300" value="${e.end||''}"></label>
 <label>Duration: <b id="f_dur"></b></label>
 <label>Venue<input id="f_venue" value="${esc(e.venue)}"></label><label>Description<textarea id="f_description" rows="3">${esc(e.description)}</textarea></label>
 <label>Session type<select id="f_stype">${TYPES.map(t=>`<option value="${t.id}" ${t.id==typeOf(e).id?'selected':''}>${t.name}</option>`).join('')}</select></label>
 <label>Status<select id="f_status"><option value="scheduled">Scheduled</option><option value="cancelled" ${e.status=='cancelled'?'selected':''}>Cancelled</option></select></label>
 ${e.kind=='exam'?'<div class="warn">Examination time is unconfirmed unless entered above.</div>':''}
 ${ser?`<label><input type="radio" name="sc" value="one" ${sr?'':'checked'} style="width:auto"> This occurrence only</label><label><input type="radio" name="sc" value="series" ${sr?'checked':''} style="width:auto"> Entire recurring series</label>`:''}
 <div class="row"><button class="btn pri" onclick="saveEv(${id||0})">Save changes</button><button class="btn" onclick="closeDrawer()">Cancel</button>
 ${id?`<button class="btn" onclick="dup(${id})">Duplicate</button><button class="btn dng" onclick="del(${id})">Delete</button>`:''}</div>`);wireTimes()}
function wireTimes(){const s=$('#f_start'),n=$('#f_end'),o=$('#f_dur');let du=mins(n.value)-mins(s.value);if(!(du>0))du=60;
 const show=()=>{const x=mins(n.value)-mins(s.value);o.textContent=!s.value||!n.value?'time not set':x>0?`${Math.floor(x/60)?Math.floor(x/60)+' h ':''}${x%60?x%60+' min':''}`:'invalid – end must be after start'};
 s.oninput=()=>{if(s.value){const m=mins(s.value)+du;if(m<=1439)n.value=hhmm(m)}show()};n.oninput=()=>{const x=mins(n.value)-mins(s.value);if(x>0)du=x;show()};show()}
async function saveEv(id){const g=k=>$('#f_'+k).value,ch={};
 ['title','module_id','facilitator_id','date','start','end','venue','description','status','stype'].forEach(k=>ch[k]=g(k));
 if(!ch.title)return alert('Title required');if(!ch.date)return alert('Date required');
 if(!!ch.start!=!!ch.end||(ch.start&&ch.start>=ch.end))return alert('End time must be later than start time (or leave both empty).');
 const cf=conflicts({id,...ch});if(cf.length&&!confirm('Scheduling conflict with: '+cf.map(c=>c.title).join('; ')+'\nSave anyway?'))return;
 if(id){await api('events/'+id,'PUT',{changes:ch,scope:document.querySelector('input[name=sc]:checked')?.value})}else await api('events','POST',{...ch,kind:NEWK});
 dr('');load()}
async function dup(id){const e=S.d.events.find(x=>x.id==id);await api('events','POST',{title:e.title+' (copy)',module_id:e.module_id,facilitator_id:e.facilitator_id,venue:e.venue,description:e.description,date:e.date,start:e.start,end:e.end});dr('');load()}
async function del(id){if(!confirm('Delete this event? It can be restored from Activity History.'))return;await api('events/'+id,'DELETE');dr('');load()}
async function act(a){await api(a,'POST');load()}
function facCard(id){const f=fac(id);dr(`<div style="text-align:center">${av(f,80)}<h3>${esc(f.name)}</h3><p>${esc(f.designation)}</p><p>${esc(mod(f.module_id)?.code||'')}</p><p>${esc(f.contact)}</p></div><div class="row"><button class="btn" onclick="facForm(${id})">Edit profile</button><button class="btn" onclick="closeDrawer()">Close</button></div>`)}
function facForm(id){const f=id?fac(id):{};dr(`<h3>${id?'Edit':'New'} facilitator</h3>
 <div class="avrow">${id?av(f,88):''}<div>${id?`<button class="btn" onclick="facPhoto(${id})">${f.avatar?'Change photo':'Add photo'}</button>${f.avatar?`<button class="btn" onclick="rmAv(${id})">Remove photo</button>`:''}`:'<small>Save the facilitator first, then add a photo.</small>'}</div></div>
 <label>Full name (titles allowed, e.g. Dr. D Mzinza)<input id="g_name" value="${esc(f.name)}"></label><label>Academic designation<input id="g_designation" value="${esc(f.designation)}"></label>
 <label>Assigned module<select id="g_module_id">${opts(S.d.modules,f.module_id,m=>m.code)}</select></label><label>Contact / details<input id="g_contact" value="${esc(f.contact)}"></label>
 <div class="row"><button class="btn pri" onclick="saveFac(${id||0})">Save</button><button class="btn" onclick="closeDrawer()">Cancel</button>${id?`<button class="btn dng" onclick="delFac(${id})">Delete</button>`:''}</div>`)}
async function saveFac(id){const ch={};['name','designation','module_id','contact'].forEach(k=>ch[k]=$('#g_'+k).value.trim());if(!ch.name)return alert('Name required');
 if(id){await api('facilitators/'+id,'PUT',ch);dr('');load()}else{const r=await api('facilitators','POST',ch);await load();facForm(r.id)}}
function facPhoto(id){avEditor('Photo – '+fac(id).name,async(blob,out,prog)=>{await uploadAvatar(id,blob,prog);await load();dr('')},()=>facForm(id))}
function meAvatar(){avEditor('Your profile photo',async(blob,out,prog)=>{const t=document.createElement('canvas');t.width=t.height=192;t.getContext('2d').drawImage(out,0,0,192,192);localStorage.editorAv=t.toDataURL('image/jpeg',.85);prog(100);dr('');render()},()=>dr(''))}
const meChip=()=>{const n=S.staffName||localStorage.editor||'';return n?(localStorage.editorAv?`<img class="av" style="width:28px;height:28px" src="${localStorage.editorAv}" alt="">`:`<span class="av ini" style="width:28px;height:28px;font-size:11px">${esc(ini(n))}</span>`)+`<small>${esc(n)}</small>`:''};
function uploadAvatar(id,blob,prog){return new Promise((res,rej)=>{const x=new XMLHttpRequest(),fd=new FormData();fd.append('file',blob,'avatar.jpg');x.open('POST',`/api/facilitators/${id}/avatar`);x.timeout=60000;x.setRequestHeader('Authorization','Bearer '+(sessionStorage.ctoken||''));
 x.setRequestHeader('Authorization','Bearer '+(sessionStorage.ctoken||''));x.upload.onprogress=e=>e.lengthComputable&&prog(Math.round(e.loaded/e.total*100));
 x.onload=()=>{if(x.status<300)res(JSON.parse(x.responseText));else{let m='Upload failed ('+x.status+').';try{m=JSON.parse(x.responseText).detail||m}catch(_){}rej(new Error(m))}};
 x.onerror=()=>rej(new Error('Cannot reach the server. Is the backend running?'));x.ontimeout=()=>rej(new Error('Upload timed out.'));x.send(fd)})}
const decodeImg=b=>new Promise((res,rej)=>{const u=URL.createObjectURL(b),i=new Image();i.onload=()=>{URL.revokeObjectURL(u);res(i)};i.onerror=()=>{URL.revokeObjectURL(u);rej(new Error('decode'))};i.src=u});
function avEditor(title,onSave,onBack){
 let img=null,rot=0,zoom=1,ox=0,oy=0,stream=null,facing='user',src='file';const SZ=280,$$=i=>document.getElementById(i);
 const stop=()=>{stream&&stream.getTracks().forEach(t=>t.stop());stream=null};
 const leave=()=>{stop();onBack()};const msg=(m,bad)=>{const e=$$('av_msg');if(e){e.textContent=m;e.style.color=bad?'var(--danger)':'var(--ink)'}};
 const on=(id,ev,f)=>{const e=$$(id);if(e)e.addEventListener(ev,f)};
 function home(){stop();dr(`<h3>${esc(title)}</h3><div id="av_drop" class="drop"><p>Drag a photo here, or</p><label class="btn pri" tabindex="0">Choose file<input type="file" id="av_file" accept="image/*,.heic,.heif" hidden></label> <button class="btn" id="av_cam">Use camera</button><p><small>JPG, PNG, WebP or HEIC (phone photos are fine)</small></p></div><div id="av_msg" role="alert"></div><div class="row"><button class="btn" id="av_back">Cancel</button></div>`);
  const d=$$('av_drop');['dragover','dragenter'].forEach(t=>d.addEventListener(t,e=>{e.preventDefault();d.classList.add('over')}));['dragleave','drop'].forEach(t=>d.addEventListener(t,()=>d.classList.remove('over')));
  d.addEventListener('drop',e=>{e.preventDefault();load(e.dataTransfer.files[0])});on('av_file','change',e=>load(e.target.files[0]));on('av_cam','click',()=>{src='cam';cam()});on('av_back','click',leave)}
 async function load(f){if(!f)return;if(!/^image\//.test(f.type)&&!/\.(jpe?g|png|webp|heic|heif)$/i.test(f.name))return msg('That file is not an image.',1);msg('Reading image…');src='file';
  try{img=await decodeImg(f)}catch(_){try{const fd=new FormData();fd.append('file',f,f.name);const r=await fetch('/api/convert',{method:'POST',headers:{Authorization:'Bearer '+(sessionStorage.ctoken||'')},body:fd});if(!r.ok){let m='Could not read this image.';try{m=(await r.json()).detail||m}catch(_){}throw new Error(m)}img=await decodeImg(await r.blob())}catch(e){return msg(e.message=='Failed to fetch'?'Cannot reach the server to convert this image.':e.message,1)}}
  rot=0;zoom=1;ox=oy=0;crop()}
 function cam(){dr(`<h3>${esc(title)}</h3><video id="av_vid" class="vid" autoplay playsinline muted></video><div id="av_msg" role="alert"></div><div class="row"><button class="btn pri" id="av_snap">Capture</button><button class="btn" id="av_sw">Switch camera</button><button class="btn" id="av_x">Cancel</button></div>`);
  on('av_x','click',home);on('av_sw','click',()=>{facing=facing=='user'?'environment':'user';start()});
  on('av_snap','click',async()=>{const v=$$('av_vid');if(!v.videoWidth)return msg('Camera is not ready yet.',1);const c=document.createElement('canvas');c.width=v.videoWidth;c.height=v.videoHeight;c.getContext('2d').drawImage(v,0,0);stop();
   c.toBlob(async b=>{img=await decodeImg(b);shot(URL.createObjectURL(b))},'image/jpeg',.92)});start()}
 async function start(){stop();if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia)return msg('Camera needs a secure page (https or localhost) and a supported browser. Choose a file instead.',1);
  try{stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:facing},audio:false});$$('av_vid').srcObject=stream}catch(e){msg(e.name=='NotAllowedError'?'Camera permission was denied. Allow camera access in the browser or choose a file.':`No usable camera found (${e.name}).`,1)}}
 function shot(u){dr(`<h3>${esc(title)}</h3><img src="${u}" class="vid" alt="Captured photo"><div class="row"><button class="btn pri" id="av_use">Use photo</button><button class="btn" id="av_re">Retake</button><button class="btn" id="av_x">Cancel</button></div>`);
  on('av_use','click',()=>{rot=0;zoom=1;ox=oy=0;crop()});on('av_re','click',cam);on('av_x','click',home)}
 function draw(c,size){const k=size/SZ,sw=rot%2?img.height:img.width,sh=rot%2?img.width:img.height,base=Math.max(SZ/sw,SZ/sh)*zoom,mx=Math.max(0,(sw*base-SZ)/2),my=Math.max(0,(sh*base-SZ)/2);ox=Math.max(-mx,Math.min(mx,ox));oy=Math.max(-my,Math.min(my,oy));
  c.save();c.fillStyle='#000';c.fillRect(0,0,size,size);c.translate(size/2+ox*k,size/2+oy*k);c.rotate(rot*Math.PI/2);c.scale(base*k,base*k);c.drawImage(img,-img.width/2,-img.height/2);c.restore()}
 function paint(){const c=$$('av_cv').getContext('2d');draw(c,SZ);c.save();c.fillStyle='rgba(0,0,0,.6)';c.beginPath();c.rect(0,0,SZ,SZ);c.arc(SZ/2,SZ/2,SZ/2-6,0,7);c.fill('evenodd');c.strokeStyle='#d4a640';c.lineWidth=2;c.beginPath();c.arc(SZ/2,SZ/2,SZ/2-6,0,7);c.stroke();c.restore()}
 function crop(){dr(`<h3>${esc(title)}</h3><canvas id="av_cv" class="cropcv" width="${SZ}" height="${SZ}" aria-label="Drag to reposition"></canvas><label>Zoom<input type="range" id="av_z" min="1" max="4" step="0.01" value="${zoom}"></label>
  <div class="row"><button class="btn" id="av_rl" title="Rotate left">⟲ Rotate</button><button class="btn" id="av_rr" title="Rotate right">⟳ Rotate</button><button class="btn" id="av_rs">Reset</button></div>
  <progress id="av_p" max="100" value="0" hidden style="width:100%"></progress><div id="av_msg" role="alert"></div>
  <div class="row"><button class="btn pri" id="av_save">Save photo</button><button class="btn" id="av_other">${src=='cam'?'Retake':'Choose another'}</button><button class="btn" id="av_cx">Cancel</button></div>`);
  const cv=$$('av_cv');let d=null;paint();cv.addEventListener('pointerdown',e=>{d=[e.clientX,e.clientY,ox,oy];cv.setPointerCapture(e.pointerId)});
  cv.addEventListener('pointermove',e=>{if(d){const r=SZ/cv.getBoundingClientRect().width;ox=d[2]+(e.clientX-d[0])*r;oy=d[3]+(e.clientY-d[1])*r;paint()}});cv.addEventListener('pointerup',()=>d=null);
  on('av_z','input',e=>{zoom=+e.target.value;paint()});on('av_rl','click',()=>{rot=(rot+3)%4;paint()});on('av_rr','click',()=>{rot=(rot+1)%4;paint()});on('av_rs','click',()=>{rot=0;zoom=1;ox=oy=0;$$('av_z').value=1;paint()});
  on('av_other','click',()=>src=='cam'?cam():home());on('av_cx','click',leave);
  on('av_save','click',async()=>{const bt=[...document.querySelectorAll('#drawer .btn')];bt.forEach(b=>b.disabled=true);const p=$$('av_p');p.hidden=false;p.value=0;msg('Saving…');
   const out=document.createElement('canvas');out.width=out.height=512;draw(out.getContext('2d'),512);
   try{const blob=await new Promise((r,j)=>out.toBlob(b=>b?r(b):j(new Error('Could not process the image.')),'image/jpeg',.9));await onSave(blob,out,v=>p.value=v)}
   catch(e){bt.forEach(b=>b.disabled=false);msg(e.message||'Saving failed.',1)}})}
 home()}
async function rmAv(id){await api(`facilitators/${id}/avatar`,'DELETE');dr('');load()}
async function delFac(id){if(confirm('Delete this facilitator?')){await api('facilitators/'+id,'DELETE');dr('');load()}}
function modForm(id){const m=mod(id);dr(`<h3>Edit module</h3><label>Code<input id="m_code" value="${esc(m.code)}"></label><label>Name<input id="m_name" value="${esc(m.name)}"></label><label>Colour<input type="color" id="m_color" value="${m.color}"></label>
 <div class="row"><button class="btn pri" onclick="saveMod(${id})">Save</button><button class="btn" onclick="closeDrawer()">Cancel</button></div>`)}
async function saveMod(id){await api('modules/'+id,'PUT',{code:$('#m_code').value,name:$('#m_name').value,color:$('#m_color').value});dr('');load()}
/* ---------- drag / resize ---------- */
document.addEventListener('pointerdown',e=>{const el=e.target.closest('.ev');if(!el||e.target.closest('.av'))return;
 const ev=S.d.events.find(x=>x.id==el.dataset.id),rs=e.target.classList.contains('rs'),cols=[...document.querySelectorAll('.col')],cw=cols[0].getBoundingClientRect().width;
 const x0=e.clientX,y0=e.clientY,s0=mins(ev.start),e0=mins(ev.end),di=cols.findIndex(c=>c.dataset.date==ev.date);let moved=false,ns=s0,ne=e0,nd=di;
 const mv=m=>{const dy=Math.round((m.clientY-y0)/PX*60/SNAP)*SNAP;if(Math.abs(m.clientY-y0)+Math.abs(m.clientX-x0)>4)moved=true;if(!moved)return;
  if(rs){ne=Math.min(T1,Math.max(s0+SNAP,e0+dy))}else{ns=Math.min(T1-(e0-s0),Math.max(T0,s0+dy));ne=ns+e0-s0;nd=Math.min(6,Math.max(0,di+Math.round((m.clientX-x0)/cw)))}
  el.style.top=(ns-T0)/60*PX+'px';el.style.height=(ne-ns)/60*PX+'px'};
 const up=async()=>{removeEventListener('pointermove',mv);removeEventListener('pointerup',up);
  if(!moved)return S.edit?form(ev.id):details(ev.id);
  const ch={start:hhmm(ns),end:hhmm(ne),date:cols[nd].dataset.date},cf=conflicts({id:ev.id,...ch});
  if(cf.length&&!confirm('Scheduling conflict with: '+cf.map(c=>c.title).join('; ')+'\nKeep this change?'))return load();
  await api('events/'+ev.id,'PUT',{changes:ch,scope:'one'});load()};
 addEventListener('pointermove',mv);addEventListener('pointerup',up);e.preventDefault()});
/* ---------- full dashboard export (canvas -> PNG / PDF, no extra libraries) ---------- */
async function dashCanvas(){
 const SC=2,SW=300,MW=1500,P=28,X=SW+P,W=SW+MW,w=S.w,d=dashData(w),imgs={},GW=MW-2*P;
 await Promise.all(S.d.facilitators.filter(f=>f.avatar).map(f=>new Promise(r=>{const a=new Image();a.onload=()=>{imgs[f.id]=a;r()};a.onerror=r;a.src='/uploads/'+f.avatar})));
 if(document.fonts)await document.fonts.ready;
 const cv=document.createElement('canvas');cv.width=W*SC;cv.height=4200*SC;let x=cv.getContext('2d');x.scale(SC,SC);x.fillStyle=V('--bg');x.fillRect(0,0,W,4200);
 const T=(t,px,py,f,c)=>{x.font=f;x.fillStyle=c;x.fillText(t,px,py)};
 const wr=(t,px,py,mw,lh,f,c)=>{x.font=f;x.fillStyle=c;let l='';for(const wd of String(t).split(' ')){const tt=l?l+' '+wd:wd;if(x.measureText(tt).width>mw&&l){x.fillText(l,px,py);py+=lh;l=wd}else l=tt}x.fillText(l,px,py);return py+lh};
 const avc=(f,cx,cy,r)=>{x.save();x.beginPath();x.arc(cx,cy,r,0,7);x.clip();if(imgs[f.id])x.drawImage(imgs[f.id],cx-r,cy-r,2*r,2*r);else{x.fillStyle='#f1e3bd';x.fillRect(cx-r,cy-r,2*r,2*r);T(ini(f.name),cx-r*.6,cy+r*.35,`bold ${r}px Georgia`,'#14213d')}x.restore();x.strokeStyle='#b8892b';x.beginPath();x.arc(cx,cy,r,0,7);x.stroke()};
 const box=(cx,cy,cw,ch)=>{x.fillStyle=V('--card');x.fillRect(cx,cy,cw,ch);x.strokeStyle=V('--line');x.strokeRect(cx,cy,cw,ch)};
 const card=(cx,cy,cw,ch,t,ls)=>{box(cx,cy,cw,ch);T(t.toUpperCase(),cx+12,cy+22,'bold 11px Georgia','#b8892b');let y=cy+44;(ls.length?ls:['None']).forEach((l,i)=>{y=wr(l,cx+12,y,cw-24,16,(i==0&&ls===d.week)?'bold 14px Georgia':'13px Georgia',V('--ink'))+2})};
 let y=40;T(S.d.settings.title,X,y,'bold 28px Georgia',V('--ink'));T(`${wkName(w)}: ${range(w)}`,X,y+28,'18px Georgia','#b8892b');x.strokeStyle='#b8892b';x.lineWidth=2;x.beginPath();x.moveTo(X,y+42);x.lineTo(W-P,y+42);x.stroke();x.lineWidth=1;y+=62;
 const cw=(GW-4*14)/5,ch=165;[['Current academic week',d.week],['Sessions this week',d.sess],['Upcoming examinations',d.exams],['Recurring activities',d.rec],['Facilitators',d.facs]].forEach(([t,l],i)=>card(X+i*(cw+14),y,cw,ch,t,l));y+=ch+14;
 const uh=44+Math.max(d.up.length,1)*18+8;card(X,y,GW,uh,'Upcoming academic activities',d.up);y+=uh+18;
 /* weekly timetable */
 const LW=56,CW=(GW-LW)/7,evs=d.ev,un=evs.filter(e=>!e.start),GH=(T1-T0)/60*PX;
 box(X,y,GW,44+30+GH);x.fillStyle=V('--head');x.fillRect(X,y,GW,44);
 for(let i=0;i<7;i++){const dd=dayN(w*7+i);T(DAYS[i],X+LW+i*CW+8,y+19,'bold 14px Georgia',V('--headink'));T(F(dd,{day:'numeric',month:'long'}),X+LW+i*CW+8,y+37,'12px Georgia',V('--headink'))}
 for(let i=0;i<7;i++)un.filter(e=>e.date==iso(dayN(w*7+i))).forEach((e,k)=>{x.fillStyle=color(e);x.fillRect(X+LW+i*CW+3,y+48+k*0,CW-6,22);T('⚠ '+e.title.slice(0,24)+' (time n/c)',X+LW+i*CW+7,y+63,'11px Georgia','#fff')});
 const gy=y+74;
 for(let h=0;h<=(T1-T0)/60;h++){x.strokeStyle=V('--line');x.beginPath();x.moveTo(X+LW-4,gy+h*PX);x.lineTo(X+GW,gy+h*PX);x.stroke();T(hhmm(T0+h*60),X+8,gy+h*PX+4,'11px Georgia',V('--muted'))}
 for(let i=0;i<=7;i++){x.strokeStyle=V('--line');x.beginPath();x.moveTo(X+LW+i*CW,y);x.lineTo(X+LW+i*CW,gy+GH);x.stroke()}
 for(let i=0;i<7;i++){const ds=iso(dayN(w*7+i));for(const e of lanes(evs.filter(q=>q.date==ds&&q.start))){const p=pos(e);if(!p)continue;const lw=CW/e._n,ex=X+LW+i*CW+e._l*lw+2,ey=gy+p.top,ew=lw-4,f=fac(e.facilitator_id),m=mod(e.module_id);
  x.save();x.beginPath();x.rect(ex,ey,ew,p.h);x.clip();const ik=inkFor(color(e));x.fillStyle=color(e);x.fillRect(ex,ey,ew,p.h);x.fillStyle=m?m.color:'rgba(0,0,0,.3)';x.fillRect(ex,ey,5,p.h);
  let ty=wr(e.title+(e.status=='cancelled'?' (cancelled)':''),ex+6,ey+14,ew-10,13,'bold 12px Georgia',ik);ty=wr(`${e.start}–${e.end}${m?' · '+m.code:''}`,ex+6,ty,ew-10,13,'11px Georgia',ik);
  if(f){avc(f,ex+14,ty+8,8);wr(f.name,ex+26,ty+12,ew-34,12,'11px Georgia',ik)}x.restore()}}
 y=gy+GH+26;
 /* legend, facilitators, notices */
 T('CALENDAR LEGEND – MODULES','X'.length?X:X,y,'bold 12px Georgia','#b8892b');y+=10;
 S.d.modules.forEach((m,i)=>{const cx=X+(i%2)*(GW/2),cy=y+Math.floor(i/2)*24;x.fillStyle=m.color;x.fillRect(cx,cy,14,14);T(`${m.code} – ${m.name}`.slice(0,70),cx+22,cy+12,'12px Georgia',V('--ink'))});y+=Math.ceil(S.d.modules.length/2)*24+4;
 T('SESSION TYPES (module shown as left stripe)',X,y,'bold 12px Georgia','#b8892b');y+=10;TYPES.forEach((t,i)=>{const cx=X+(i%3)*(GW/3),cy=y+Math.floor(i/3)*24;x.fillStyle=typeColor(t);x.fillRect(cx,cy,14,14);T(t.name,cx+22,cy+12,'12px Georgia',V('--ink'))});y+=Math.ceil(TYPES.length/3)*24+14;
 T('FACILITATOR DETAILS','X'.length?X:X,y,'bold 12px Georgia','#b8892b');y+=14;
 if(!S.d.facilitators.length){T('No facilitators have been added yet.',X,y+14,'13px Georgia',V('--ink'));y+=26}
 S.d.facilitators.forEach(f=>{avc(f,X+18,y+18,16);T(f.name,X+44,y+14,'bold 13px Georgia',V('--ink'));T([f.designation,mod(f.module_id)?.code,f.contact].filter(Boolean).join(' · '),X+44,y+32,'12px Georgia',V('--muted'));y+=44});y+=8;
 const cf=evs.filter(e=>conflicts(e).length).length,nt=S.d.events.filter(e=>e.kind=='exam'&&!e.start).length;
 T('ACADEMIC NOTICES','X'.length?X:X,y,'bold 12px Georgia','#b8892b');y+=18;
 y=wr(`${cf?cf+' session(s) this week are flagged for scheduling conflicts.':'No scheduling conflicts this week.'} ${nt?nt+' examination(s) have no confirmed time.':''}`,X,y,GW,16,'13px Georgia',V('--ink'));y+=10;
 T(`Exported ${new Date().toLocaleString('en-GB')} · ${wkName(w)} (${range(w)})`,X,y+8,'11px Georgia',V('--muted'));const H=Math.ceil(y+40);
 /* final canvas + sidebar */
 const out=document.createElement('canvas');out.width=W*SC;out.height=H*SC;const o=out.getContext('2d');o.drawImage(cv,0,0,W*SC,H*SC,0,0,W*SC,H*SC);x=o;x.setTransform(SC,0,0,SC,0,0);
 x.fillStyle=V('--side');x.fillRect(0,0,SW,H);T('PhD in Maternal',20,46,'20px Georgia','#f1e3bd');T('and Neonatal Health',20,70,'20px Georgia','#f1e3bd');T('ACADEMIC CALENDAR 2026',20,92,'11px Georgia','#b8892b');
 x.fillStyle='#b8892b';x.fillRect(20,104,SW-40,1);let sy=132;
 SIDE().forEach(it=>{if(it.w==null){if(it.k=='dashboard'){x.fillStyle='rgba(255,255,255,.08)';x.fillRect(0,sy-20,SW,30);x.fillStyle='#d4a640';x.fillRect(0,sy-20,3,30)}T(it.n,20,sy,'14px Georgia',it.k=='dashboard'?'#f3eee2':'#d9dde6');sy+=30}
  else{const i=it.w;if(i==w){x.fillStyle='rgba(212,166,64,.22)';x.fillRect(28,sy-16,SW-44,38);x.strokeStyle='#d4a640';x.strokeRect(28,sy-16,SW-44,38)}T(wkName(i),40,sy,'bold 12px Georgia','#f3eee2');T(range(i),40,sy+14,'11px Georgia','#c3cad6');sy+=44}});
 x.fillStyle='#b8892b';x.fillRect(20,H-74,SW-40,1);T('Penrose ScholarMW',20,H-44,'bold 16px Georgia','#f1e3bd');T('Advancing academic excellence',20,H-24,'11px Georgia','#b8892b');
 return out}
const dl=(b,n)=>{const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=n;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),4000)};
async function downloadProtected(url,name){const r=await fetch(url,{headers:{Authorization:'Bearer '+(sessionStorage.ctoken||'')}});if(!r.ok){let j={};try{j=await r.json()}catch(_){}throw new Error(j.detail||'Download failed ('+r.status+')')}dl(await r.blob(),name)}
async function pngExport(){const c=await dashCanvas();c.toBlob(b=>dl(b,`dashboard-week${11+S.w}.png`))}
function pdfBlob(cv){const jpg=atob(cv.toDataURL('image/jpeg',.93).split(',')[1]),W=1190,H=Math.round(W*cv.height/cv.width),parts=[],off=[];let len=0;const add=s=>{parts.push(s);len+=s.length};
 const obj=(n,s)=>{off[n]=len;add(`${n} 0 obj\n${s}\nendobj\n`)};add('%PDF-1.4\n');obj(1,'<</Type/Catalog/Pages 2 0 R>>');obj(2,'<</Type/Pages/Kids[3 0 R]/Count 1>>');
 obj(3,`<</Type/Page/Parent 2 0 R/MediaBox[0 0 ${W} ${H}]/Resources<</XObject<</Im 4 0 R>>>>/Contents 5 0 R>>`);
 off[4]=len;add(`4 0 obj\n<</Type/XObject/Subtype/Image/Width ${cv.width}/Height ${cv.height}/ColorSpace/DeviceRGB/BitsPerComponent 8/Filter/DCTDecode/Length ${jpg.length}>>\nstream\n`);add(jpg);add('\nendstream\nendobj\n');
 const c=`q ${W} 0 0 ${H} 0 0 cm /Im Do Q`;obj(5,`<</Length ${c.length}>>\nstream\n${c}\nendstream`);
 const xr=len;add('xref\n0 6\n0000000000 65535 f \n'+[1,2,3,4,5].map(n=>String(off[n]).padStart(10,'0')+' 00000 n \n').join('')+`trailer\n<</Size 6/Root 1 0 R>>\nstartxref\n${xr}\n%%EOF`);
 const s=parts.join(''),u=new Uint8Array(s.length);for(let i=0;i<s.length;i++)u[i]=s.charCodeAt(i)&255;return new Blob([u],{type:'application/pdf'})}
async function pdfExport(){dl(pdfBlob(await dashCanvas()),`dashboard-week${11+S.w}.pdf`)}
/* ---------- events ---------- */
document.addEventListener('click',async e=>{const t=e.target,q=s=>t.closest(s);
 if(!q('.dl'))$('#dlmenu').hidden=true;
 if(q('#pw')||q('#nw')){S.w=Math.min(NWK()-1,Math.max(0,S.w+(q('#nw')?1:-1)));S.view=S.view=='dashboard'?'dashboard':'weekly';render()}else if(q('#today')){const k=Math.floor((new Date(TODAY()+'T00:00:00Z')-dayN(0))/864e5/7);S.w=Math.min(NWK()-1,Math.max(0,k));render()}else if(q('[data-go]')){S.view=q('[data-go]').dataset.go;render()}else if(q('#menu')){document.body.classList.toggle(innerWidth<800?'so':'sc')}else if(q('#dlbtn'))$('#dlmenu').hidden=!$('#dlmenu').hidden;
 else if(q('[data-x]')){const x=q('[data-x]').dataset.x;$('#dlmenu').hidden=true;if(x=='png')pngExport();else if(x=='pdf')pdfExport();else await downloadProtected(`/api/export/${x}?week=${S.w}`,`week${11+S.w}.${x}`)}
 else if(q('[data-backup]'))await downloadProtected('/api/backup','calendar-backup.json');
 else if(q('[data-ics]'))await downloadProtected('/api/ics','calendar.ics');
 else if(q('[data-w]')){if(S.edit&&e.shiftKey){const w=+q('[data-w]').dataset.w,n=prompt('Week label',wkName(w));if(n)await api('settings/0','PUT',{['wk'+w]:n}),load();return}S.w=+q('[data-w]').dataset.w;S.view='weekly';dr('');render()}
 else if(q('[data-v]')){S.view=q('[data-v]').dataset.v;dr('');render()}
 else if(q('.av[data-fac]'))facCard(q('.av').dataset.fac);
 else if(q('.ev')||q('.chip[data-id]')){if(q('.chip'))S.edit?form(+q('.chip').dataset.id):details(+q('.chip').dataset.id)}
 else if(q('.col')&&!q('.ev')&&S.edit&&canEditCalendar()){const c=q('.col'),y=e.clientY-c.getBoundingClientRect().top,s=T0+Math.floor(y/PX*60/SNAP)*SNAP;form(0,{date:c.dataset.date,start:hhmm(s),end:hhmm(Math.min(s+120,T1))})}
 else if(q('[data-mod]'))modForm(+q('[data-mod]').dataset.mod);
 else if(q('[data-fac-edit]'))facForm(+q('[data-fac-edit]').dataset.facEdit);
 else if(q('[data-fac-new]'))facForm(0);
 else if(q('[data-restore]')){await api(`history/${q('[data-restore]').dataset.restore}/restore`,'POST');load()}
 else if(q('[data-ed]'))form(+q('[data-ed]').dataset.ed,{scope:q('[data-ed]').dataset.sc})
 else if(q('[data-newex]'))form(0,{kind:'exam'})
 else if(q('#tgl')&&canEditCalendar()){S.edit=!S.edit;render()}
 else if(q('#sv')){localStorage.editor=$('#ed').value.trim();if(!localStorage.editor)delete localStorage.editor;await api('settings/0','PUT',{title:$('#pt').value});load()}else if(q('#calendarSignOut')){sessionStorage.removeItem('ctoken');load()}
 else if(q('#undo'))act('undo');else if(q('#redo'))act('redo')});
document.addEventListener('change',async e=>{const t=e.target;if(t.id=='theme'||t.id=='themeS'){setTheme(t.value);return}if(t.id=='cbg'){localStorage.bgc=t.value;setTheme('custom');return}if(t.classList&&t.classList.contains('tcol')){await api('settings/0','PUT',{['tc_'+t.dataset.t]:t.value});load();return}if(e.target.id=='rst'){const r=await api('restore','POST',JSON.parse(await e.target.files[0].text()));load()}});
document.addEventListener('dblclick',async e=>{if(S.edit&&e.target.id=='ttl'){const n=prompt('Programme title',S.d.settings.title);if(n){await api('settings/0','PUT',{title:n});load()}}});
let BUSY=false;for(const n of ['saveEv','saveFac','dup','del','saveMod','delFac','rmAv']){const o=window[n];window[n]=async(...a)=>{if(BUSY)return;BUSY=true;const bt=[...document.querySelectorAll('#drawer .btn')];bt.forEach(b=>b.disabled=true);try{await o(...a)}catch(e){if(e)console.error(e)}finally{BUSY=false;bt.forEach(b=>b.disabled=false)}}}
addEventListener('keydown',e=>{if(e.key=='Escape'){$('#dlmenu').hidden=true;closeDrawer()}});$('#drawer').addEventListener('input',()=>{DIRTY=true});
applyTheme();$('#theme').innerHTML=THEMES.map(t=>`<option value="${t.id}">${t.name}</option>`).join('');$('#theme').value=curTheme();
load();
