from common import *
u=read(ROOT/'api_usage.json');u['latency_measurement_scope']='SDK-provider wrapper includes network request, response deserialization and proposal parsing; measured_non_transport_case_seconds is the remainder outside that wrapper, not all CPU processing.';write(ROOT/'api_usage.json',u)
