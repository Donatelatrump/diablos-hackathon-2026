// Local Chromium QA. No personal browser profile, no external publication.
const {chromium}=require('./tmp/responsive-qa/node_modules/playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const baseline=process.argv.includes('--baseline');
const quick=process.argv.includes('--quick');
const output=path.resolve('reports/responsive_2026_10_29',baseline?'baseline':'final');
fs.mkdirSync(output,{recursive:true});
const profiles=[{name:'small',width:320,height:740,mobile:true},
 {name:'android',width:360,height:800,mobile:true},{name:'phone',width:390,height:844,mobile:true},
 {name:'large-phone',width:430,height:932,mobile:true},{name:'landscape',width:844,height:390,mobile:true},
 {name:'tablet',width:768,height:1024,mobile:true},{name:'desktop',width:1440,height:1000,mobile:false}]
 .filter(p=>!quick||['small','phone','desktop'].includes(p.name));

async function audit(page){
 return page.evaluate(()=>{
  const main=document.querySelector('[data-testid="stMain"]');
  const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>8&&r.height>8&&s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0';};
  const buttons=[...document.querySelectorAll('.st-key-main-menu button,.st-key-pitch-presets button,.st-key-start-hand-choice button,[data-testid="stFormSubmitButton"] button')].filter(visible).map(e=>{
   const r=e.getBoundingClientRect();return {text:e.textContent.trim(),x:r.x,y:r.y,width:r.width,height:r.height};});
  const overflow=[...main.querySelectorAll('*')].filter(visible).filter(e=>!e.closest('[data-testid="stDataFrame"],[role="tablist"]')).map(e=>{
   const r=e.getBoundingClientRect();return {tag:e.tagName,testid:e.dataset.testid,cls:typeof e.className==='string'?e.className.slice(0,100):'',text:(e.textContent||'').slice(0,70),left:r.left,right:r.right};
  }).filter(r=>r.left<-.5||r.right>innerWidth+.5).slice(0,20);
  return {viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
   mainWidth:main?.clientWidth,mainScrollWidth:main?.scrollWidth,buttons,overflow,
   pitchCardWidth:document.querySelector('.st-key-start-pitch-card')?.getBoundingClientRect().width};
 });
}

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--enable-unsafe-swiftshader']});
 const results=[];
 try{
  for(const profile of profiles){
   const context=await browser.newContext({viewport:{width:profile.width,height:profile.height},isMobile:profile.mobile,hasTouch:profile.mobile,deviceScaleFactor:1,reducedMotion:'reduce'});
   const page=await context.newPage();const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto('http://127.0.0.1:8501',{waitUntil:'domcontentloaded'});
   await page.locator('.st-key-start-pitch-card').waitFor({timeout:60000});
   await page.evaluate(async()=>{await document.fonts.ready;return true;});
   const iframe=await page.locator('.st-key-start-visual iframe').elementHandle({timeout:30000});
   const visual=await iframe.contentFrame();
   await visual.locator('#scene').waitFor({timeout:30000});
   await visual.waitForFunction(()=>document.querySelector('#status')?.textContent!=='Preparando lanzamiento',null,{timeout:30000});
   const initial=await audit(page);
   await page.screenshot({path:path.join(output,profile.name+'-top.png')});
   let scene;
   for(const frame of page.frames()){
    if(await frame.locator('#scene').count()){
     await frame.waitForFunction(()=>document.querySelector('#status')?.textContent!=='Preparando lanzamiento',{timeout:15000}).catch(()=>{});
     scene=await frame.evaluate(()=>{
      const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
      const title=rect(document.querySelector('h2')),badge=rect(document.querySelector('#speed'));
      const controls=document.querySelector('.controls');
      return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,height:innerHeight,bodyHeight:document.body.scrollHeight,note:rect(document.querySelector('.note')),title,badge,
       overlap:title.left<badge.right&&title.right>badge.left&&title.top<badge.bottom&&title.bottom>badge.top,
       controlsWidth:controls.clientWidth,controlsScrollWidth:controls.scrollWidth,
       touchAction:getComputedStyle(document.querySelector('#scene')).touchAction,
       unavailable:getComputedStyle(document.querySelector('#unavailable')).display!=='none',
       buttons:[...document.querySelectorAll('.controls button,.controls select')].map(e=>({id:e.id,...rect(e)}))};
     });
     await page.locator('.st-key-start-visual').screenshot({path:path.join(output,profile.name+'-viewer.png')});
     break;
    }
   }
   results.push({profile,initial,scene,errors});
   fs.writeFileSync(path.join(output,'audit.json'),JSON.stringify(results,null,2));
   console.log(JSON.stringify({profile:profile.name,width:initial.viewport,scroll:initial.mainScrollWidth,overflow:initial.overflow.length,scene:scene&&{overlap:scene.overlap,touchAction:scene.touchAction,width:scene.width,scrollWidth:scene.scrollWidth,unavailable:scene.unavailable}}));
   if(!baseline){
    assert(initial.mainScrollWidth<=initial.viewport+1,profile.name+' page overflow');
    if(profile.width<=1000) assert(initial.pitchCardWidth>=profile.width-85,profile.name+' narrow form');
    assert(!scene.overlap,profile.name+' title overlaps speed');
    assert(scene.scrollWidth<=scene.width+1,profile.name+' viewer overflow');
    assert.equal(scene.touchAction,'pan-y');
    assert(scene.note.bottom<=scene.height+1,profile.name+' clipped explanatory note');
    assert(!scene.unavailable,profile.name+' WebGL unavailable');
    assert(initial.buttons.every(b=>b.height>=44),profile.name+' small touch target');
    if(profile.name==='phone'){
     await page.locator('.st-key-start-visual iframe').evaluate(e=>e.scrollIntoView({block:'start'}));
     await page.locator('[data-testid="stMain"]').evaluate(e=>e.scrollTop-=90);
     await page.screenshot({path:path.join(output,'phone-viewer-top.png')});
     const main=page.locator('[data-testid="stMain"]');
     const before=await main.evaluate(e=>e.scrollTop);
     const box=await visual.locator('#scene').boundingBox();
     const cdp=await context.newCDPSession(page);
     const x=Math.round(box.x+box.width/2),y=Math.round(box.y+260);
     await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});
     for(let step=1;step<=8;step++){
      await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:y-step*20}]});
      await page.waitForTimeout(25);
     }
     await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
     await page.waitForTimeout(300);
     const swipeDelta=await main.evaluate(e=>e.scrollTop)-before;
     assert(swipeDelta>30,'Swipe over the 3D field must scroll the page');
     await cdp.detach();
     await visual.locator('#play').tap();
     assert.equal(await visual.locator('#play').textContent(),'Pausar');
     await visual.locator('#play').tap();
     await visual.locator('#replay').tap();
     await visual.locator('#camera').selectOption('side');
     await visual.locator('#rate').selectOption('1');
     await page.getByRole('button',{name:'Curva',exact:true}).tap();
     await page.locator('.st-key-start-hand-Right button').tap();
     await page.getByRole('button',{name:'Ver evaluación del lanzamiento',exact:true}).tap();
     await page.locator('.st-key-start-result-card').waitFor({timeout:60000});
     await page.locator('.st-key-start-result-card').evaluate(e=>e.scrollIntoView({block:'start'}));
     await main.evaluate(e=>e.scrollTop-=80);
     await page.screenshot({path:path.join(output,'phone-result.png')});
     const sections=[];
     for(const name of ['Comparar estadios','Lanzadores','Confianza','Ayuda','Simulador']){
      await page.locator('.st-key-main-menu').getByRole('button',{name,exact:true}).tap();
      await page.waitForFunction(()=>!document.querySelector('[data-testid="stStatusWidget"]'));
      await page.waitForTimeout(1200);
      const layout=await audit(page);
      assert(layout.mainScrollWidth<=layout.viewport+1,name+' page overflow');
      assert.equal(await page.locator('[data-testid="stException"]').count(),0,name+' app exception');
      await page.screenshot({path:path.join(output,'phone-'+name.replaceAll(' ','-')+'.png')});
      sections.push({name,...layout});
     }
     fs.writeFileSync(path.join(output,'phone-interactions.json'),JSON.stringify({viewerControls:true,swipeDelta,presetAndHand:true,evaluation:true,sections},null,2));
    }
   }
   await context.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
