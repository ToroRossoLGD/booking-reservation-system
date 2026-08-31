import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AccountDashboard } from "./Dashboard";

const apiMock = vi.hoisted(() => ({
  notifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  dismissNotification: vi.fn(),
  dismissReadNotifications: vi.fn(),
}));

vi.mock("./api", () => ({ api: apiMock }));

const unread = {
  id: 11,
  title: "Booking confirmed",
  message: "Your reservation is ready.",
  is_read: false,
  created_at: "2026-08-31T10:00:00Z",
};

const read = {
  id: 12,
  title: "Payment received",
  message: "Thank you for your payment.",
  is_read: true,
  created_at: "2026-08-30T10:00:00Z",
};

function renderNotifications() {
  return render(
    <AccountDashboard
      user={{ id: 7, email: "guest@example.com", role: "customer" }}
      initialTab="notifications"
      onExplore={vi.fn()}
      onOpenReservation={vi.fn()}
      onCloseReservation={vi.fn()}
    />,
  );
}

describe("AccountDashboard notification inbox", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.notifications.mockResolvedValue({
      items: [unread, read],
      total: 2,
      limit: 50,
      offset: 0,
      has_next: false,
    });
  });

  it("marks an individual notification as read and updates the unread count", async () => {
    apiMock.markNotificationRead.mockResolvedValue({ ...unread, is_read: true });
    const user = userEvent.setup();
    renderNotifications();

    await screen.findByText("Booking confirmed");
    expect(screen.getByText("1 unread")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Mark read" }));

    await waitFor(() => expect(apiMock.markNotificationRead).toHaveBeenCalledWith(11));
    expect(screen.getByText("0 unread")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark read" })).not.toBeInTheDocument();
  });

  it("dismisses one notification and clears only read notifications", async () => {
    apiMock.dismissNotification.mockResolvedValue(undefined);
    apiMock.dismissReadNotifications.mockResolvedValue({ dismissed_count: 1 });
    const user = userEvent.setup();
    renderNotifications();

    const payment = await screen.findByText("Payment received");
    const paymentCard = payment.closest("article");
    expect(paymentCard).not.toBeNull();
    await user.click(within(paymentCard!).getByRole("button", { name: "Dismiss" }));

    await waitFor(() => {
      expect(apiMock.dismissNotification).toHaveBeenCalledWith(12);
      expect(screen.queryByText("Payment received")).not.toBeInTheDocument();
    });

    apiMock.dismissReadNotifications.mockResolvedValue({ dismissed_count: 0 });
    expect(screen.getByRole("button", { name: "Clear read" })).toBeDisabled();
    expect(screen.getByText("Booking confirmed")).toBeInTheDocument();
  });

  it("marks all notifications read and then clears them", async () => {
    apiMock.markAllNotificationsRead.mockResolvedValue(undefined);
    apiMock.dismissReadNotifications.mockResolvedValue({ dismissed_count: 2 });
    const user = userEvent.setup();
    renderNotifications();

    await screen.findByText("Booking confirmed");
    await user.click(screen.getByRole("button", { name: "Mark all read" }));

    await waitFor(() => expect(apiMock.markAllNotificationsRead).toHaveBeenCalledOnce());
    expect(screen.getByText("0 unread")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear read" }));

    await waitFor(() => expect(apiMock.dismissReadNotifications).toHaveBeenCalledOnce());
    expect(screen.getByText("You’re all caught up")).toBeInTheDocument();
    expect(screen.getByText("2 read notifications cleared.")).toBeInTheDocument();
  });
});
