// Run after generating yuwen-jiaocan.html. Uses file:// to exercise true offline mode.
const {chromium}=require('playwright');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.BROWSER_PATH?{executablePath:process.env.BROWSER_PATH}:{})});
  try{
    for(const viewport of [{width:1280,height:900},{width:390,height:844}]){
      const context=await browser.newContext({viewport});const page=await context.newPage();const errors=[];
      page.on('pageerror',e=>errors.push(e.message));
      await page.goto(pathToFileURL(path.resolve(__dirname,'../yuwen-jiaocan.html')).href);
      await page.locator('#menu').click();await page.locator('#search').fill('赤壁赋');await page.locator('#search').press('Enter');
      await page.waitForFunction(()=>document.querySelector('#count').textContent.startsWith('命中'));
      const first=page.locator('#tree .doc').first();assert.match(await first.textContent(),/赤壁赋/);assert.ok(await first.locator('small').count());
      await first.click();await page.locator('#links button').filter({hasText:'参考译文'}).first().click();
      assert.equal(await page.locator('#title').textContent(),'《赤壁赋》参考译文');assert.match(await page.locator('#content').textContent(),/壬戌年的秋天/);
      assert.doesNotMatch(await page.locator('#content').textContent(),/泰山的南面/);assert.match(await page.locator('#source').textContent(),/101–106/);
      await page.locator('#font').selectOption('21');
      await page.locator('#content p').last().scrollIntoViewIfNeeded();await page.waitForTimeout(300);const scroll=await page.evaluate(()=>scrollY);
      await page.reload();await page.waitForFunction(()=>document.querySelector('#title').textContent==='《赤壁赋》参考译文');
      assert.equal(await page.locator('#font').inputValue(),'21');await page.waitForTimeout(300);assert.ok(Math.abs((await page.evaluate(()=>scrollY))-scroll)<30);
      await page.locator('#links button').filter({hasText:'查看原文位置'}).click();assert.equal(await page.locator('#title').textContent(),'资料链接');
      await page.locator('#menu').click();await page.locator('#search').fill('清风');await page.locator('#search').press('Enter');await page.locator('#tree .doc').first().click();
      assert.ok(await page.locator('#content mark').count());assert.equal(await page.locator('#matches').isVisible(),true);await page.locator('#next').click();
      await page.locator('#menu').click();await page.locator('#search').fill('');await page.locator('#search').press('Enter');await page.locator('#books button').first().click();
      const details=page.locator('#tree details').first();assert.equal(await details.getAttribute('open'),null);await details.locator('summary').click();assert.notEqual(await details.getAttribute('open'),null);
      await page.keyboard.press('Escape');assert.equal(await page.locator('#side').isVisible(),false);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
      if(process.env.SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCREENSHOT_DIR,`reader-${viewport.width}.png`)});
      await context.close();console.log(`PASS offline reader ${viewport.width}x${viewport.height}`);
    }
    const context=await browser.newContext();const page=await context.newPage();
    await page.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw Error('disabled');}});});
    await page.goto(pathToFileURL(path.resolve(__dirname,'../yuwen-jiaocan.html')).href);await page.locator('#menu').click();assert.equal(await page.locator('#side').isVisible(),true);
    await context.close();console.log('PASS storage-disabled startup');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
