// Requires npm install --prefix frontend and an installed Playwright Chromium.
// Optionally set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH to your Chromium executable.
const {chromium}=require('../frontend/node_modules/@playwright/test');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--single-process']});
 try {
  const page=await browser.newPage({viewport:{width:1400,height:1000}}), errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.resolve(__dirname,'../research/cfm/generated/coverage_map.html')).href);
  await page.getByRole('button',{name:'Chromepet',exact:true}).click();
  if(await page.locator('#cases article').count()!==2)throw Error('Wrong case count');
  await page.locator('#cases summary').first().click();
  if(!await page.locator('#cases details').first().evaluate(e=>e.open))throw Error('Evidence did not expand');
  await page.locator('#stations button').first().click();
  if(!(await page.locator('#detail').innerText()).includes('historical rows'))throw Error('Missing station detail');
  await page.selectOption('#family','AWS');
  if(!(await page.locator('#stations').innerText()).includes('AWS'))throw Error('Filter failed');
  await page.getByRole('button',{name:'Velachery',exact:true}).click();
  await page.selectOption('#family','all');
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('PASS: atlas interactions, mobile layout, no JS errors.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
