import {test,expect,type Page} from "@playwright/test";
async function open(page:Page){await page.goto("/#simulation");await expect(page.getByRole("heading",{name:/Before the response/})).toBeVisible();}
async function next(page:Page){await page.getByRole("button",{name:"Next event",exact:true}).click();}
async function evidence(page:Page){await page.getByRole("button",{name:"Why? Check the evidence"}).first().click();}
async function savePlan(page:Page){const drawer=page.getByRole("dialog");await drawer.getByRole("button",{name:"We can help"}).click();await drawer.getByRole("button",{name:"Save contribution"}).click();await expect(page.locator(".sim-plan-card").first()).toBeVisible();}
async function checks(page:Page){const d=page.getByRole("dialog");await d.getByLabel("Training contact and demand checked").check();await d.getByLabel("Training access checked").check();await d.getByLabel("Training receiving time agreed").check();const approve=d.getByRole("button",{name:"Approve contribution",exact:true});if(await approve.isEnabled())await approve.click();}

test("waterlogging walkthrough approves, detects source changes, resumes and resets without live records",async({page},info)=>{
 test.setTimeout(60000);
 await open(page);await page.screenshot({path:info.outputPath("simulation-lobby.png"),fullPage:true,animations:"disabled"});
 await page.getByRole("button",{name:/From report to response/}).click();
 await expect(page.getByRole("heading",{name:"Start with what is known."})).toBeVisible();
 await next(page);await expect(page.locator(".sim-request")).toContainText("Unreviewed");
 await evidence(page);await expect(page.getByRole("dialog")).toContainText("No coordinator check");await savePlan(page);
 await page.locator(".sim-plan-card").first().click();await checks(page);await expect(page.getByRole("dialog")).toContainText("awaiting review");await expect(page.getByRole("button",{name:"Approve contribution",exact:true})).toBeDisabled();await page.getByRole("button",{name:"Close drawer"}).click();
 await next(page);await page.getByRole("button",{name:/Local requests/}).click();await expect(page.locator(".sim-request")).toContainText("Coordinator-reviewed");
 await page.getByRole("button",{name:/The rainfall number alone/}).click();await expect(page.locator(".sim-decision-feedback")).toContainText("Reconsider");await page.getByRole("button",{name:/A current reviewed need/}).click();await expect(page.locator(".sim-decision-feedback")).toContainText("Exactly");
 await page.screenshot({path:info.outputPath("simulation-reviewed-desktop.png"),fullPage:true,animations:"disabled"});
 await evidence(page);await expect(page.getByRole("dialog")).toContainText("120 litres requested · 80 available");await page.screenshot({path:info.outputPath("simulation-evidence-desktop.png"),animations:"disabled"});await savePlan(page);
 await page.locator(".sim-plan-card").first().click();await checks(page);await expect(page.locator(".sim-plan-card").first()).toContainText("Practice approved");
 await next(page);await expect(page.locator(".sim-plan-card").first()).toContainText("Source changed");
 await page.reload();await expect(page.getByRole("heading",{name:/Before the response/})).toBeVisible();await page.getByRole("button",{name:"Resume saved session"}).click();await expect(page.getByRole("heading",{name:"Your old plan needs a fresh look."})).toBeVisible();
 await next(page);await expect(page.locator(".sim-request")).toContainText("80 litres");
 await next(page);await expect(page.locator(".sim-request")).toContainText("Resolved");await expect(page.locator(".sim-outcome")).toContainText("0fictional requests still open");
 await page.getByRole("button",{name:"Reset scenario",exact:true}).click();await expect(page.getByRole("heading",{name:"Start with what is known."})).toBeVisible();await expect(page.locator(".sim-request")).toHaveCount(0);
 await page.getByRole("button",{name:"Return to live",exact:true}).click();await expect(page.getByRole("heading",{name:"Where can your team help?"})).toBeVisible();await expect(page.locator(".request-card").filter({hasText:"SIMULATION"})).toHaveCount(0);
});

test("rain scenario cannot approve preparedness and ends with rejected claim",async({page})=>{
 await open(page);await page.getByRole("button",{name:/Rain is not a rescue call/}).click();
 await page.getByRole("button",{name:"Save a preparedness draft"}).click();await page.getByRole("button",{name:"Save contribution"}).click();await page.locator(".sim-plan-card").click();await checks(page);await expect(page.getByRole("dialog")).toContainText("cannot be approved");await expect(page.getByRole("button",{name:"Approve contribution",exact:true})).toBeDisabled();await page.getByRole("button",{name:"Close drawer"}).click();
 for(let i=0;i<5;i++){await next(page);await expect(page.locator(".sim-timeline li").nth(i+1)).toHaveAttribute("aria-current","step");}
 await page.getByRole("button",{name:/Local requests/}).click();await expect(page.locator(".sim-request")).toContainText("Rejected");await expect(page.locator(".sim-request")).toContainText("No outstanding quantity established");
});

test("three area story stays usable on mobile, keeps rescue visible and exports labelled plan",async({page},info)=>{
 await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:"reduce"});await open(page);await page.getByRole("button",{name:/Three areas. One team/}).click();await next(page);await next(page);
 await expect(page.locator(".sim-request")).toHaveCount(3);await expect(page.locator(".sim-request.urgent")).toContainText("Trained rescue requested");await expect(page.locator(".sim-request.urgent")).toContainText("food");
 await page.getByRole("button",{name:/Focus Tambaram/}).click();await expect(page.locator(".sim-request")).toHaveCount(1);await evidence(page);await expect(page.getByRole("dialog")).toContainText("does not qualify your team for flood rescue");await savePlan(page);await page.locator(".sim-plan-card").click();const download=page.waitForEvent("download");await page.getByRole("button",{name:"Export training briefing"}).click();expect((await download).suggestedFilename()).toMatch(/^SIMULATION-/);await page.getByRole("button",{name:"Close drawer"}).click();
 await page.getByRole("button",{name:/Local requests/}).click();await page.getByRole("button",{name:"All areas",exact:true}).click();await page.screenshot({path:info.outputPath("simulation-mobile.png"),fullPage:true,animations:"disabled"});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 for(let i=0;i<3;i++)await next(page);
 await expect(page.locator(".sim-outcome")).toContainText("2fictional requests still open");await expect(page.locator(".sim-outcome")).toContainText("Tambaram, Chromepet");
});


test("scenario chooser is always reachable and resuming is explicit",async({page})=>{
 await open(page);await page.getByRole("button",{name:/From report to response/}).click();await next(page);
 await page.getByRole("button",{name:"Choose scenario",exact:true}).click();
 await expect(page.getByRole("heading",{name:/Before the response/})).toBeVisible();
 await page.getByRole("button",{name:"Resume saved session"}).click();
 await expect(page.getByRole("heading",{name:"People report a specific need."})).toBeVisible();
 await page.getByRole("button",{name:"Return to live",exact:true}).click();
 await page.getByRole("button",{name:/Try a simulation/}).click();
 await expect(page.getByRole("heading",{name:/Before the response/})).toBeVisible();
 await page.getByRole("button",{name:/From report to response/}).click();
 await expect(page.getByRole("heading",{name:"Start with what is known."})).toBeVisible();
 await expect(page.locator(".sim-request")).toHaveCount(0);
 await page.getByRole("button",{name:"Choose scenario",exact:true}).click();
 await page.getByRole("button",{name:/Rain is not a rescue call/}).click();
 await expect(page.getByRole("heading",{name:"A forecast is a reason to check."})).toBeVisible();
});
