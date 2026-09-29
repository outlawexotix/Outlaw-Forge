#!/usr/bin/env python3
"""
Outlaw Forge - Independent Smoke & Health Verification Harness
==============================================================
Validates running backend API instance against contract schemas,
HTTP status codes, latency thresholds, and CORS policies.

Usage:
    python tests/verify_health.py
    python tests/verify_health.py --base-url http://127.0.0.1:8000 --timeout 5
"""

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class HealthVerifier:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.results: List[Tuple[str, bool, str]] = []

    def log_step(self, title: str):
        print(f"\n{Colors.BOLD}{Colors.CYAN}> [TEST CASE] {title}{Colors.RESET}")

    def assert_test(self, name: str, condition: bool, details: str = ""):
        if condition:
            print(f"  {Colors.GREEN}[PASS]{Colors.RESET} {name} {f'({details})' if details else ''}")
            self.results.append((name, True, details))
        else:
            print(f"  {Colors.RED}[FAIL]{Colors.RESET} {name} - {details}")
            self.results.append((name, False, details))

    def _http_request(
        self, endpoint: str, method: str = "GET", headers: Dict[str, str] = None
    ) -> Tuple[int, Dict[str, str], bytes, float]:
        url = f"{self.base_url}{endpoint}"
        req_headers = headers or {}
        req = urllib.request.Request(url, method=method, headers=req_headers)

        start_time = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                res_headers = dict(resp.headers)
                body = resp.read()
                return resp.status, res_headers, body, elapsed_ms
        except urllib.error.HTTPError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            res_headers = dict(e.headers)
            body = e.read()
            return e.code, res_headers, body, elapsed_ms
        except urllib.error.URLError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            raise ConnectionError(f"Failed to connect to {url}: {e.reason}") from e

    def verify_schema(self, data: Dict[str, Any], context: str) -> bool:
        """Strictly validates HealthStatusResponse schema according to API contract."""
        required_root_keys = {
            "status",
            "version",
            "app_name",
            "environment",
            "services",
            "system",
            "timestamp",
        }
        missing_root = required_root_keys - set(data.keys())
        self.assert_test(
            f"{context} root keys complete",
            len(missing_root) == 0,
            f"Missing: {missing_root}" if missing_root else "All 7 schema keys present",
        )

        # Status validation
        status_val = data.get("status")
        self.assert_test(
            f"{context} status enum valid",
            status_val in ["healthy", "degraded", "unhealthy"],
            f"status = '{status_val}'",
        )

        # App name & version
        app_name = data.get("app_name")
        version = data.get("version")
        self.assert_test(
            f"{context} identity metadata",
            app_name == "Outlaw Forge" and isinstance(version, str) and len(version) > 0,
            f"app_name='{app_name}', version='{version}'",
        )

        # Services structure
        services = data.get("services", {})
        self.assert_test(
            f"{context} services structure",
            isinstance(services, dict)
            and "database" in services
            and "mesh_engine" in services,
            f"services: {services}",
        )
        if isinstance(services, dict):
            self.assert_test(
                f"{context} database status enum",
                services.get("database") in ["connected", "disconnected"],
                f"database = '{services.get('database')}'",
            )
            self.assert_test(
                f"{context} mesh_engine status enum",
                services.get("mesh_engine") in ["ready", "unavailable"],
                f"mesh_engine = '{services.get('mesh_engine')}'",
            )

        # System info
        system = data.get("system", {})
        self.assert_test(
            f"{context} system info structure",
            isinstance(system, dict)
            and "platform" in system
            and "python_version" in system,
            f"platform='{system.get('platform')}', python='{system.get('python_version')}'",
        )

        # Timestamp validation
        timestamp_str = data.get("timestamp", "")
        valid_iso = False
        try:
            datetime.datetime.fromisoformat(timestamp_str)
            valid_iso = True
        except Exception as e:
            valid_iso = False
        self.assert_test(
            f"{context} ISO 8601 UTC timestamp",
            valid_iso,
            f"timestamp = '{timestamp_str}'",
        )

        return True

    def run_all_checks(self) -> bool:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}{'='*65}")
        print(f" OUTLAW FORGE API HEALTH VERIFICATION SUITE")
        print(f" Target Host: {self.base_url}")
        print(f"{'='*65}{Colors.RESET}\n")

        # 1. Root Endpoint Test
        self.log_step("Root API Discovery (/ endpoint)")
        try:
            status, headers, body, latency = self._http_request("/")
            self.assert_test("Root endpoint HTTP 200", status == 200, f"Status: {status}, Latency: {latency:.2f}ms")
            content_type = headers.get("content-type", "")
            self.assert_test("Content-Type application/json", "application/json" in content_type, content_type)
            data = json.loads(body.decode("utf-8"))
            self.assert_test("Root payload discovery links", "docs_url" in data and "health_url" in data, f"payload keys: {list(data.keys())}")
        except Exception as e:
            self.assert_test("Root endpoint connectivity", False, str(e))

        # 2. Main /health Endpoint Test
        self.log_step("Root Health Probe (/health endpoint)")
        try:
            status, headers, body, latency = self._http_request("/health")
            self.assert_test("Health endpoint HTTP 200", status == 200, f"Status: {status}, Latency: {latency:.2f}ms")
            self.assert_test("Response latency within SLO (<100ms)", latency < 100.0, f"{latency:.2f}ms")
            content_type = headers.get("content-type", "")
            self.assert_test("Content-Type is JSON", "application/json" in content_type, content_type)
            data = json.loads(body.decode("utf-8"))
            self.verify_schema(data, context="[/health]")
        except Exception as e:
            self.assert_test("Health endpoint connectivity", False, str(e))

        # 3. Versioned /api/v1/health Endpoint Test
        self.log_step("Versioned API Health Probe (/api/v1/health endpoint)")
        try:
            status, headers, body, latency = self._http_request("/api/v1/health")
            self.assert_test("Versioned health HTTP 200", status == 200, f"Status: {status}, Latency: {latency:.2f}ms")
            data = json.loads(body.decode("utf-8"))
            self.verify_schema(data, context="[/api/v1/health]")
        except Exception as e:
            self.assert_test("Versioned health connectivity", False, str(e))

        # 4. CORS Header Verification
        self.log_step("CORS Policy Verification (Origin: http://localhost:3000)")
        try:
            status, headers, _, _ = self._http_request(
                "/health",
                headers={"Origin": "http://localhost:3000"}
            )
            cors_header = headers.get("access-control-allow-origin") or headers.get("Access-Control-Allow-Origin")
            self.assert_test(
                "Access-Control-Allow-Origin present",
                cors_header in ["http://localhost:3000", "*"],
                f"access-control-allow-origin = '{cors_header}'",
            )
        except Exception as e:
            self.assert_test("CORS verification error", False, str(e))

        # Summary
        total = len(self.results)
        passed = sum(1 for _, ok, _ in self.results if ok)
        failed = total - passed

        print(f"\n{Colors.BOLD}{Colors.YELLOW}{'='*65}")
        print(" VERIFICATION SUMMARY")
        print(f"{'='*65}{Colors.RESET}")
        print(f"Total Tests Executed : {total}")
        print(f"Passed               : {Colors.GREEN}{passed}{Colors.RESET}")
        print(f"Failed               : {Colors.RED if failed > 0 else Colors.GREEN}{failed}{Colors.RESET}")

        if failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}[OK] ALL ACCEPTANCE CRITERIA SATISFIED FOR HEALTH ENDPOINTS.{Colors.RESET}\n")
            return True
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}[FAIL] VERIFICATION FAILED ({failed} checks failed).{Colors.RESET}\n")
            return False


def main():
    parser = argparse.ArgumentParser(description="Outlaw Forge Health & Contract Verification Harness")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of running Outlaw Forge backend instance (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Request timeout in seconds (default: 5.0)",
    )
    args = parser.parse_args()

    verifier = HealthVerifier(base_url=args.base_url, timeout=args.timeout)
    success = verifier.run_all_checks()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
