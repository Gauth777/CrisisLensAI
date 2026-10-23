import {test,expect} from "@playwright/test";
test("welcoming homepage exposes measured safeguards without claiming model accuracy",async({page},info)=>{
 test.setTimeout(60000);
 await page.route("https://tile.openstreetmap.org/**",route=>route.fulfill({contentType:"image/png",body:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=","base64")}));
 await page.goto("/");await expect(page.getByRole("heading",{name:/A little help/})).toBeVisible();await page.screenshot({path:info.outputPath("community-home-desktop.png"),fullPage:true,animations:"disabled"});
 await page.getByRole("button",{name:"Our evidence",exact:true}).click();await expect(page.getByRole("dialog")).toContainText("10 / 10");await expect(page.getByRole("dialog")).toContainText("not an accuracy score");await page.screenshot({path:info.outputPath("evidence-checks.png"),animations:"disabled"});await page.getByRole("button",{name:"Close drawer"}).click();
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:info.outputPath("community-home-mobile.png"),fullPage:true,animations:"disabled"});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
test("conflict scenario holds quantities and displays both records",async({page})=>{
 await page.goto("/#simulation");await page.getByRole("button",{name:/The stories don’t agree/}).click();await page.getByRole("button",{name:"Next event",exact:true}).click();await page.getByRole("button",{name:"Next event",exact:true}).click();await expect(page.locator(".sim-request")).toHaveCount(2);await expect(page.locator(".sim-request").first()).toContainText("Conflicting reports");await page.getByRole("button",{name:"Why? Check the evidence"}).first().click();await expect(page.getByRole("dialog")).toContainText("Reports disagree about access");await page.getByRole("button",{name:"Prepare a practice plan"}).click();await page.getByRole("button",{name:"Save practice draft"}).click();await page.locator(".sim-plan-card").click();await expect(page.getByRole("dialog")).toContainText("Proposal withheld");
});
