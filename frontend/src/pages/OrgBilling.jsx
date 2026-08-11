import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import api from "../api";
import AppHeader from "../components/AppHeader";
import "../styles/Dashboard.css";
import "../styles/Billing.css";

export default function OrgBilling() {
  const { slug } = useParams();
  const titleId = useId();
  const [searchParams, setSearchParams] = useSearchParams();
  const paypalHandled = useRef(false);

  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirmPlan, setConfirmPlan] = useState(null);
  const [resultModal, setResultModal] = useState(null);
  const [checkoutBusy, setCheckoutBusy] = useState(false);

  const loadBilling = useCallback(() => {
    setLoading(true);
    setError("");
    return api
      .get(`/api/organizations/${slug}/billing/`)
      .then((res) => setData(res.data))
      .catch((err) => {
        setData(null);
        const detail =
          err.response?.data?.detail ||
          (err.response
            ? `Billing request failed (${err.response.status}).`
            : "Could not reach the billing API. Check that the backend is running.");
        setError(detail);
      })
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    loadBilling();
  }, [loadBilling]);

  useEffect(() => {
    setConfirmPlan(null);
    setResultModal(null);
    setCheckoutBusy(false);
    paypalHandled.current = false;
  }, [slug]);

  // PayPal browser return: record subscription id, never treat as activated.
  useEffect(() => {
    const paypal = searchParams.get("paypal");
    if (!paypal || paypalHandled.current) return;

    if (paypal === "cancelled") {
      paypalHandled.current = true;
      setResultModal({
        title: "Checkout cancelled",
        body: "PayPal checkout was cancelled. No payment was processed.",
        emphasis: "Your organization service was not changed.",
      });
      const next = new URLSearchParams(searchParams);
      next.delete("paypal");
      setSearchParams(next, { replace: true });
      return;
    }

    if (paypal !== "success") return;

    paypalHandled.current = true;
    const subscriptionId =
      searchParams.get("subscription_id") ||
      searchParams.get("subscriptionId") ||
      "";

    const finishSuccessUi = (extra = {}) => {
      const activated = Boolean(extra.activated);
      setResultModal({
        title: activated ? "Subscription active" : "Subscription submitted",
        body: activated
          ? "PayPal confirmed your subscription. Your organization's paid service is now active."
          : "Your PayPal subscription has been received. CommuniB is confirming your subscription.",
        emphasis: activated
          ? `Effective service: ${extra.effective || "paid"}.`
          : "Paid service activates after PayPal confirms the subscription. Refresh this page if it still shows pending.",
        ...extra,
      });
      const next = new URLSearchParams(searchParams);
      next.delete("paypal");
      next.delete("subscription_id");
      next.delete("subscriptionId");
      next.delete("ba_token");
      next.delete("token");
      setSearchParams(next, { replace: true });
    };

    if (!subscriptionId) {
      // Manual ?paypal=success must not activate anything.
      finishSuccessUi();
      loadBilling();
      return;
    }

    api
      .post(`/api/organizations/${slug}/billing/paypal/confirm/`, {
        subscription_id: subscriptionId,
      })
      .then((res) => {
        finishSuccessUi({
          activated: res.data.activated,
          reference: res.data.service?.billing_reference
            || res.data.pending_service?.billing_reference,
          effective: res.data.effective_service_level,
        });
      })
      .catch((err) => {
        setError(
          err.response?.data?.detail ||
            "Could not record the PayPal return. Service was not activated."
        );
        finishSuccessUi();
      })
      .finally(() => {
        loadBilling();
      });
  }, [searchParams, setSearchParams, slug, loadBilling]);

  const closeModals = () => {
    if (checkoutBusy) return;
    setConfirmPlan(null);
    setResultModal(null);
  };

  const handleChoosePlan = (plan) => {
    if (plan.checkout_mode === "contact") {
      return;
    }
    setResultModal(null);
    setConfirmPlan(plan);
  };

  const handleContinueCheckout = async () => {
    if (!confirmPlan || checkoutBusy) return;
    setCheckoutBusy(true);
    setError("");
    try {
      const res = await api.post(`/api/organizations/${slug}/billing/checkout/`, {
        service_level: confirmPlan.service_level,
      });

      if (res.data.approve_url) {
        window.location.assign(res.data.approve_url);
        return;
      }

      const checkout = res.data.checkout;
      const pending = res.data.pending_service;
      setConfirmPlan(null);
      setResultModal({
        title: "Checkout recorded",
        body: `A PENDING ${checkout.name} checkout was saved (${checkout.price_display}).`,
        reference: pending?.billing_reference,
        emphasis: `No payment was processed. Effective service remains ${
          res.data.effective_service_level || "FREE"
        }.`,
      });
      await loadBilling();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Could not start checkout for this organization."
      );
      setConfirmPlan(null);
    } finally {
      setCheckoutBusy(false);
    }
  };

  const orgName = data?.organization?.name;
  const current = data?.current_service;
  const pending = data?.pending_checkout;
  const paypalReady = data?.checkout_mode === "paypal";

  return (
    <div className="dashboard">
      <AppHeader />
      <main className="dashboard-main billing-page">
        <Link to={`/dashboard/${slug}`} className="dashboard-back">
          ← Back to organization
        </Link>

        {loading && <p className="dashboard-empty">Loading...</p>}
        {error && <p className="dashboard-error">{error}</p>}

        {data && (
          <>
            <div className="dashboard-header">
              <h1>Billing &amp; Service</h1>
              <p className="billing-org-name">{orgName}</p>
            </div>

            {data.paypal_sandbox && (
              <div
                className="billing-sandbox-banner"
                role="status"
                aria-live="polite"
              >
                Sandbox mode is activated. No PayPal transaction will take
                place.
              </div>
            )}

            <section className="billing-current" aria-labelledby={`${titleId}-current`}>
              <h2 id={`${titleId}-current`} className="billing-section-title">
                Current Service
              </h2>
              <div className="billing-current-card">
                <p className="billing-current-name">{current?.name}</p>
                <p className="billing-current-level">{current?.service_level}</p>
                {current?.status && (
                  <p className="billing-current-status">Status: {current.status}</p>
                )}
              </div>
            </section>

            {pending && (
              <section
                className="billing-pending"
                aria-labelledby={`${titleId}-pending`}
              >
                <h2 id={`${titleId}-pending`} className="billing-section-title">
                  Pending Checkout
                </h2>
                <div className="billing-current-card">
                  <p className="billing-current-name">{pending.name}</p>
                  <p className="billing-current-level">{pending.status}</p>
                  <p className="billing-current-status">
                    Reference: {pending.billing_reference}
                  </p>
                  {pending.paypal_subscription_id && (
                    <p className="billing-current-status">
                      PayPal subscription: {pending.paypal_subscription_id}
                    </p>
                  )}
                  <p className="billing-current-status">
                    Not active yet. CommuniB activates service after confirmation.
                  </p>
                </div>
              </section>
            )}

            <section className="billing-plans" aria-labelledby={`${titleId}-plans`}>
              <h2 id={`${titleId}-plans`} className="billing-section-title">
                Available Plans
              </h2>
              <ul className="billing-plan-list">
                {(data.plans || []).map((plan) => (
                  <li key={plan.service_level} className="billing-plan-card">
                    <div className="billing-plan-copy">
                      <h3 className="billing-plan-name">{plan.name}</h3>
                      <p className="billing-plan-price">{plan.price_display}</p>
                      <p className="billing-plan-desc">{plan.description}</p>
                    </div>
                    {data.can_manage_billing ? (
                      plan.checkout_mode === "contact" ? (
                        <Link to="/contact" className="dashboard-btn billing-plan-btn">
                          {plan.button_label}
                        </Link>
                      ) : (
                        <button
                          type="button"
                          className="dashboard-btn dashboard-btn--primary billing-plan-btn"
                          onClick={() => handleChoosePlan(plan)}
                        >
                          {plan.button_label}
                        </button>
                      )
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>

            <p className="billing-footnote">
              {data.paypal_sandbox
                ? "Sandbox mode is activated. No PayPal transaction will take place. Checkout uses the PayPal sandbox environment only."
                : paypalReady
                  ? "Choosing a plan starts PayPal checkout. Paid service stays inactive until CommuniB confirms the subscription."
                  : "PayPal is not enabled in this environment. Choosing a plan creates a PENDING checkout only and does not charge or activate service."}
            </p>
          </>
        )}
      </main>

      {confirmPlan && (
        <div
          className="billing-modal-backdrop"
          role="presentation"
          onClick={closeModals}
        >
          <div
            className="billing-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`${titleId}-confirm`}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id={`${titleId}-confirm`} className="billing-modal-title">
              Choose {confirmPlan.name}?
            </h2>
            <p className="billing-modal-plan">
              {confirmPlan.name}
              <br />
              {confirmPlan.price_display}
            </p>
            <p className="billing-modal-body">
              {data?.paypal_sandbox
                ? "This will open PayPal sandbox checkout for testing."
                : paypalReady
                  ? "This will start a PayPal subscription checkout."
                  : "This will create a pending CommuniB checkout record (PayPal is not configured here)."}
            </p>
            {data?.paypal_sandbox && (
              <div
                className="billing-sandbox-banner billing-sandbox-banner--modal"
                role="status"
              >
                Sandbox mode is activated. No PayPal transaction will take
                place.
              </div>
            )}
            <div className="billing-modal-actions">
              <button
                type="button"
                className="dashboard-btn"
                onClick={closeModals}
                disabled={checkoutBusy}
              >
                Cancel
              </button>
              <button
                type="button"
                className="dashboard-btn dashboard-btn--primary"
                onClick={handleContinueCheckout}
                disabled={checkoutBusy}
              >
                {checkoutBusy ? "Working…" : "Continue"}
              </button>
            </div>
          </div>
        </div>
      )}

      {resultModal && (
        <div
          className="billing-modal-backdrop"
          role="presentation"
          onClick={closeModals}
        >
          <div
            className="billing-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`${titleId}-result`}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id={`${titleId}-result`} className="billing-modal-title">
              {resultModal.title}
            </h2>
            <p className="billing-modal-body">{resultModal.body}</p>
            {resultModal.reference && (
              <p className="billing-modal-body">Reference: {resultModal.reference}</p>
            )}
            {resultModal.effective && (
              <p className="billing-modal-body">
                Effective service: {resultModal.effective}
              </p>
            )}
            {resultModal.emphasis && (
              <p className="billing-modal-body billing-modal-body--emphasis">
                {resultModal.emphasis}
              </p>
            )}
            <div className="billing-modal-actions">
              <button
                type="button"
                className="dashboard-btn dashboard-btn--primary"
                onClick={closeModals}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
