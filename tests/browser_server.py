"""Isolated browser-test server. Synthetic sources never enter normal app startup."""
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    import uvicorn
    from crisislens.data.operations import utcnow
    os.environ["CRISISLENS_ALERT_POLLING"]="0"
    os.environ["CRISISLENS_REVIEW_TOKEN"]="browser-test-token"
    os.environ["GROQ_API_KEY"]="browser-test-only-not-a-key"
    os.environ["CRISISLENS_PROVIDER"]="groq"
    import api
    from crisislens.workflow import Workflow
    from crisislens.data.operations import RSS
    def context(area,refresh=False):
        now=utcnow()
        source={"id":"W1","kind":"weather","title":"TEST weather source","publisher":"Open-Meteo test fixture","url":"https://api.open-meteo.com/v1/forecast","published_at":now.isoformat(),"retrieved_at":now.isoformat(),"excerpt":"TEST modelled forecast; not a real observation.","scope":"locality_grid","content_scope":"modelled_weather","limitation":"TEST ONLY; no incident confirmation."}
        return {"location":area,"retrieved_at":now.isoformat(),"outlook":{"environment":{"temperature_c":29,"observed_at":now.isoformat()},"next_rain":None,"hours":[{"time":(now+timedelta(hours=i+1)).isoformat(),"precipitation_mm":0,"probability_percent":10} for i in range(24)],"forecast_complete":True},"sources":[source],"source_status":[{"name":"Open-Meteo","status":"available"}],"coverage_note":"TEST ONLY bounded context"}
    class Provider:
        model="browser-test-model"
        def generate_json(self,**kwargs):
            data=json.loads(kwargs["user_prompt"].split('\n',1)[1])
            if 'reviews' in kwargs['output_schema']['properties']:
                return {'reviews':[{'claim_id':c['id'],'verdict':'supported','reason':'TEST ONLY scripted semantic check.','omitted_source_ids':[]} for c in data['claims']]}
            field=next((s for s in data["sources"] if s["kind"]=="field_report"),None)
            if 'headline' not in kwargs['output_schema']['properties']:
                passage=field['excerpt'] if field else ''
                claims=[{'id':'C1','statement':field['excerpt'].split('. ')[0]+'.' if field else 'TEST check local request','category':'needs','timeframe':'current','explanation':'TEST assessment of the supplied source.','next_check':'Confirm the receiving contact.','evidence':[{'source_id':field['id'],'direction':'supports','passage':passage[:300],'reason':'The test field record states the request.'}] if field else []}]
                history=next((s for s in data['sources'] if s['kind']=='historical'),None)
                if history:
                    claims.append({'id':'C2','statement':'Historical source note: '+history['title'],'category':'incident','timeframe':'historical','explanation':'Historical comparison only, not present conditions.','next_check':'','evidence':[{'source_id':history['id'],'direction':'supports','passage':history['excerpt'],'reason':'The historical record names this area.'}]})
                return {'claims':claims}
            return {"location":data["question"]["location"],"headline":"TEST: confirm receipt before preparing supplies","answer":"TEST ONLY: base the draft on the reviewed request and confirm access.","claims":[],"recommendations":[{"title":"Confirm the requested quantity","explanation":"Confirm demand with the receiving contact.","source_ids":[field["id"]] if field else [],"claim_ids":["C1"],"intent":"check"}],"affected_groups":[],"supplies":[],"missing_information":["Current street access"]}
    api.collect_context=context
    api.build_provider=lambda name:Provider()
    with tempfile.TemporaryDirectory(prefix="crisislens-browser-test-") as directory:
        os.environ["CRISISLENS_SIM_DB_DIR"]=str(Path(directory)/"simulations")
        api._operations=Workflow(Path(directory)/"test.sqlite3")
        now=utcnow(); url="https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=100"
        cap=f'''<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>TEST-cap</identifier><sender>TEST IMD Chennai</sender><sent>{now.isoformat()}</sent><status>Actual</status><scope>Public</scope><msgType>Alert</msgType><info><language>en-IN</language><event>TEST district rain warning</event><headline>TEST ONLY: illustrative warning, not real weather.</headline><certainty>Possible</certainty><severity>Moderate</severity><expires>{(now+timedelta(hours=2)).isoformat()}</expires><area><areaDesc>Chennai district</areaDesc></area></info></alert>'''.encode()
        feed=f'<rss><channel><item><author>IMD Chennai</author><link>{url}</link></item></channel></rss>'.encode()
        api._operations.poll(lambda u:feed if u==RSS else cap)
        uvicorn.run(api.app,host="127.0.0.1",port=8011,log_level="warning")
