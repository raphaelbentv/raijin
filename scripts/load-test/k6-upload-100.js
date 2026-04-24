import http from "k6/http";
import { check, sleep } from "k6";

const apiUrl = __ENV.API_URL || "http://localhost:6200";
const token = __ENV.TOKEN;
const pdfPath = __ENV.PDF_PATH || "frontend/e2e/fixtures/invoice-sprint5.pdf";

export const options = {
  scenarios: {
    upload_100_invoices_in_1m: {
      executor: "constant-arrival-rate",
      rate: 100,
      timeUnit: "1m",
      duration: "1m",
      preAllocatedVUs: 20,
      maxVUs: 100,
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<3000"],
  },
};

const pdf = open(pdfPath, "b");

export default function () {
  if (!token) {
    throw new Error("TOKEN env var is required");
  }

  const payload = {
    file: http.file(pdf, `load-${__VU}-${__ITER}.pdf`, "application/pdf"),
  };
  const res = http.post(`${apiUrl}/invoices/upload`, payload, {
    headers: { Authorization: `Bearer ${token}` },
    timeout: "20s",
  });

  check(res, {
    "upload accepted": (r) => r.status === 201 || r.status === 409,
  });
  sleep(0.1);
}
