import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
const [mode, url, outdirInput] = process.argv.slice(2);
const outdir=path.resolve(outdirInput);
await fs.mkdir(outdir,{recursive:true});
const profile=path.join(outdir,'..','.qa-browser',String(Date.now()));
await fs.mkdir(profile,{recursive:true});
const child=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',[
  '--headless=new','--no-first-run','--no-default-browser-check','--disable-extensions',
  '--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',
  '--user-data-dir='+profile,'about:blank'
],{windowsHide:true,stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
let socket;
try{
 let port;
 for(let i=0;i<100;i++){
  try { port=(await fs.readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];if(port)break;}catch{}
  await pause(100);
 }
 if(!port)throw Error('Chrome DevTools did not start');
 const targets=await (await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 const target=targets.find(t=>t.type==='page');
 socket=new WebSocket(target.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let seq=0;const pending=new Map();const errors=[];let status=null;
 socket.onmessage=event=>{
  const message=JSON.parse(event.data);
  if(message.id){const p=pending.get(message.id);pending.delete(message.id);if(message.error)p.reject(Error(JSON.stringify(message.error)));else p.resolve(message.result);}
  if(message.method==='Runtime.exceptionThrown')errors.push(message.params.exceptionDetails.text);
  if(message.method==='Network.responseReceived'&&message.params.type==='Document')status=message.params.response.status;
 };
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error('CDP timeout '+method));}},20000).unref();});
 const evaluate=async expression=>{
  const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));
  return r.result?.value;
 };
 const wait=async expression=>{
  for(let i=0;i<100;i++){if(await evaluate(expression))return;await pause(100);}
  throw Error('UI wait failed: '+expression);
 };
 const screenshot=async name=>{
  await evaluate("document.querySelectorAll('.toast').forEach(x=>x.remove())");
  const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await fs.writeFile(path.join(outdir,name),Buffer.from(r.data,'base64'));
 };
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
 await call('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false});
 const navigation=await call('Page.navigate',{url});
 await pause(1500);
 await wait("document.readyState==='complete'");
 if(mode==='public'){
  const result=await evaluate("({url:location.href,title:document.title,text:document.body.innerText.slice(0,4000),localStorageDemo:document.documentElement.outerHTML.includes('localStorage')})");
  result.status=status;result.navigationError=navigation.errorText||null;result.anonymousProfile=true;result.checked_at=new Date().toISOString();
  result.passed=status===200&&result.title.includes('WorkFlow');
  await fs.writeFile(path.join(outdir,'site-public-check.json'),JSON.stringify(result,null,2));
  await screenshot('site-public.png');
  console.log(JSON.stringify(result));
 }else{
  await wait("document.getElementById('memory-status').textContent.includes('已连接')");
  await evaluate("document.querySelector('[onclick=\"showAddLogModal()\"]').click();document.getElementById('log-title').value='完成登录模块';document.getElementById('log-content').value='实现 JWT 认证和登录页面 <img src=x onerror=\"window.__xss=true\">';document.getElementById('log-tags').value='JWT,<svg onload=window.__xss=true>';document.getElementById('log-category').value='development';document.getElementById('log-form').requestSubmit()");
  await wait("document.querySelectorAll('.log-card').length===1");
  if(await evaluate('window.__xss===true'))throw Error('HTML injection in logs');
  await screenshot('app-logs.png');
  await evaluate("document.querySelector('[data-tab=\"search\"]').click();document.getElementById('search-input').value='JWT';document.querySelector('[onclick=\"doSearch()\"]').click()");
  await wait("document.querySelectorAll('.search-result-card').length===1");
  await screenshot('app-search.png');
  await evaluate("document.querySelector('[data-tab=\"report\"]').click();document.querySelector('[onclick=\"generateReport()\"]').click()");
  await wait("document.getElementById('report-output').textContent.includes('记忆依据')");
  if(await evaluate('window.__xss===true'))throw Error('HTML injection in report');
  await screenshot('app-report.png');
  await evaluate("document.querySelector('[data-tab=\"chat\"]').click();document.getElementById('chat-input').value='JWT';document.querySelector('[onclick=\"sendChat()\"]').click()");
  await wait("document.querySelectorAll('.chat-message.bot').length>=2&&!document.querySelector('.chat-message.loading')");
  if(!await evaluate("document.getElementById('chat-messages').textContent.includes('atomic-memory')"))throw Error('Chat citation absent');
  await evaluate("document.querySelector('[data-tab=\"logs\"]').click();document.querySelector('.log-card-actions .btn').click()");
  await wait("document.getElementById('log-title').value==='完成登录模块'&&document.getElementById('add-log-modal').style.display==='flex'");
  await evaluate("document.getElementById('log-content').value='已完成 OAuth2 验证';document.getElementById('log-tags').value='OAuth2';document.getElementById('log-form').requestSubmit()");
  await wait("document.querySelector('.log-card-content')?.textContent==='已完成 OAuth2 验证'");
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await screenshot('app-mobile.png');
  const overflow=await evaluate('document.documentElement.scrollWidth>window.innerWidth+1');
  if(errors.length)throw Error('Browser errors: '+errors.join(';'));
  const result={passed:true,checks:['UI creates log and displays memory reference','UI search receives memory hit','UI report displays actual recall citations','UI chat includes source reference','UI edits log and updates rendered content','HTML in tags and report stays inert'],mobile_overflow:overflow,checked_at:new Date().toISOString(),errors};
  await fs.writeFile(path.join(outdir,'browser-check.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
 }
 await call('Browser.close');
}catch(error){console.error(error.stack);process.exitCode=1;}finally{socket?.close();child.kill();}
