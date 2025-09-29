from api.router import api_router


def test_api_router_registers_expected_routes():
    paths = {route.path for route in api_router.routes}
    assert "/validate-sequence" in paths
    assert "/design" in paths
    assert "/jobs/{job_id}" in paths
