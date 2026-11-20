from testkart_intelligence.discovery.engine import DiscoveryEngine

engine = DiscoveryEngine(db_path='data/real_world_pilot_30day.db')
for sc in ['MPPSC', 'PPSC', 'DRDO_RAC', 'OPSC']:
    res = engine.run_scan(source_code=sc, auto_enrich=False)
    print(f"{sc:<10} Scan: status={res['status']}, new={res['new_notices']}, errors={res['errors_count']}, err_summary={res['error_summary']}")
