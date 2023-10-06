import requests
from tests.helpers import NetworkTest
import time
CONTROLLER = '127.0.0.1'
KYTOS_API = 'http://%s:8181/api' % CONTROLLER


class TestE2ESDNTraceInvertedCircuit:
    net = None
    circuit = None
    @staticmethod
    def setup_class(cls):
        """run at the beginning for all tests"""
        cls.net = NetworkTest(CONTROLLER, topo_name='linear10')
        cls.net.start()
        cls.net.restart_kytos_clean()
        cls.net.wait_switches_connect()



    @classmethod
    def teardown_class(cls):
        print('somente na terminação')
        cls.net.stop()

    @staticmethod
    def create_evc(vlan_id, interface_a="00:00:00:00:00:00:00:01:1", interface_z="00:00:00:00:00:00:00:0a:1"):
        payload = {
            "name": "Vlan_%s" % vlan_id,
            "enabled": True,
            "dynamic_backup_path": True,
            "uni_a": {
                "interface_id": interface_a,
                "tag": {"tag_type": 1, "value": vlan_id}
            },
            "uni_z": {
                "interface_id": interface_z,
                "tag": {"tag_type": 1, "value": vlan_id}
            }
        }
        api_url = KYTOS_API + '/kytos/mef_eline/v2/evc/'
        response = requests.post(api_url, json=payload)
        assert response.status_code == 201, response.text
        data = response.json()
        return data['circuit_id']

        response = requests.get(api_url + "switches")
        switches = response.json()
        for switch in switches["switches"]:
            response = requests.post(api_url + f"switches/{switch}/enable")
            response = requests.post(api_url + f"interfaces/switch{switch}/enable")

        response = requests.get(api_url + "links")
        links = response.json()
        for link in links["links"]:
            response = requests.post(api_url + f"links/{link}/enable")

        time.sleep(10)

    @staticmethod
    def get_evc(circuit_id):
        api_url = KYTOS_API + '/kytos/mef_eline/v2/evc/'
        response = requests.get(api_url + circuit_id)
        assert response.status_code == 200, response.text
        data = response.json()
        return data

    def test_100_run_sdntrace_cp(self):
        """Run SDNTrace-CP (Control Plane)."""
        # Trace from UNI_A
        payload = {
            "trace": {
                "switch": {"dpid": "00:00:00:00:00:00:03:01", "in_port": 1},
                "eth": {"dl_type": 33024, "dl_vlan": 400}
            }
        }

        api_url = KYTOS_API + '/amlight/sdntrace_cp/v1/trace'
        response = requests.put(api_url, json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert "result" in data, data
        assert len(data["result"]) == 10, data

        expected = [
            (
                l['endpoint_b']['switch'],
                l['endpoint_b']['port_number'],
                l['metadata']['s_vlan']['value']
            )
            for l in self.circuit['current_path']
        ]
        expected.insert(0, ('00:00:00:00:00:00:03:1', 1, 400))

        actual = [
            (step['dpid'], step['port'], step['vlan'])
            for step in data["result"]
        ]

        assert expected == actual, f"Expected {expected}. Actual: {actual}"

        # Trace from UNI_Z
        payload = {
            "trace": {
                "switch": {"dpid": "00:00:00:00:00:00:01:1", "in_port": 1},
                "eth": {"dl_type": 33024, "dl_vlan": 400}
            }
        }
        api_url = KYTOS_API + '/amlight/sdntrace_cp/v1/trace'
        response = requests.put(api_url, json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert "result" in data
        assert len(data["result"]) == 10, data

        expected = [
            (
                l['endpoint_a']['switch'],
                l['endpoint_a']['port_number'],
                l['metadata']['s_vlan']['value']
            )
            for l in reversed(self.circuit['current_path'])
        ]
        expected.insert(0, ('00:00:00:00:00:00:01:1', 1, 400))

        actual = [
            (step['dpid'], step['port'], step['vlan'])
            for step in data["result"]
        ]

        assert expected == actual, f"Expected {expected}. Actual: {actual}"
