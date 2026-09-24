from umlpy import companion, edn, mailbox, policy
from umlpy.edn import Symbol, Vector, kw


def test_sync_order_keeps_user_order_and_proposals():
    pol = policy.new_policy("t", ".", "app", ["b", "a", "gone"])
    pol[kw("proposals")] = Vector([{kw("id"): kw("p")}])
    synced = policy.sync_order(pol, ["a", "b", "new"])
    assert synced[kw("order")] == Vector([Symbol("b"), Symbol("a"), Symbol("new")])
    assert synced[kw("proposals")] == pol[kw("proposals")]
    assert pol[kw("order")] == Vector([Symbol("b"), Symbol("a"), Symbol("gone")])


def test_policy_write_read_round_trip(tmp_path):
    path = tmp_path / ".uml-viewer/policy.edn"
    pol = policy.new_policy("t", "src", "app", ["a"])
    policy.write(path, pol)
    assert policy.read(path) == pol


def test_mail_send_then_pop_oldest_first(tmp_path):
    box = tmp_path / "to.edn"
    first = mailbox.send(box, "display", {kw("path"): "d.edn"})
    mailbox.send(box, "regen", {})
    assert first[kw("id")] == 1
    assert mailbox.pop(box)[kw("op")] == kw("display")
    assert mailbox.pop(box)[kw("op")] == kw("regen")
    assert mailbox.pop(box) is None
    assert mailbox.send(box, "regen", {})[kw("id")] == 3


def test_mail_reads_viewer_written_queue(tmp_path):
    box = tmp_path / "to-agent.edn"
    box.write_text('{:next-id 5, :queue [{:id 4, :op :context, :context :real}]}')
    assert mailbox.pop(box) == {kw("id"): 4, kw("op"): kw("context"), kw("context"): kw("real")}


def test_mail_queue_is_trimmed(tmp_path):
    box = tmp_path / "to.edn"
    for _ in range(40):
        mailbox.send(box, "regen", {})
    queue = mailbox.read(box)[kw("queue")]
    assert len(queue) == mailbox.KEEP_N and queue[0][kw("id")] == 9


def test_parse_value():
    assert mailbox.parse_value(":real") == kw("real")
    assert mailbox.parse_value("7") == 7
    assert mailbox.parse_value(".uml-viewer/diagram.edn") == ".uml-viewer/diagram.edn"


def test_companion_command_replaces_grok(tmp_path, monkeypatch):
    monkeypatch.setenv("UMLPY_CLAUDE_BIN", "/bin/echo")
    cmd = companion.command(tmp_path)
    assert cmd[0] == "/bin/echo"
    assert cmd[1:5] == companion.DEFAULT_PERMISSIONS
    assert "umlpy ir --display" in cmd[-1]
    assert "Python" in cmd[cmd.index("--append-system-prompt") + 1]


def test_companion_args_file_overrides_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("UMLPY_CLAUDE_BIN", "/bin/echo")
    (tmp_path / ".uml-viewer").mkdir()
    (tmp_path / companion.ARGS_FILE).write_text("--permission-mode plan")
    assert companion.command(tmp_path)[1:3] == ["--permission-mode", "plan"]


def test_deliver_returns_once_viewer_takes_command(tmp_path):
    box = tmp_path / "to-viewer.edn"
    cmd, delivered = mailbox.deliver(box, "display", {}, sleep=lambda _: mailbox.pop(box))
    assert delivered and cmd[kw("id")] == 1


def test_deliver_resends_when_viewer_treats_command_as_stale(tmp_path):
    box = tmp_path / "to-viewer.edn"
    ticks = []

    def viewer_ready_after_first_send(_):
        ticks.append(1)
        if len(ticks) == 2:
            mailbox.pop(box)
            mailbox.pop(box)

    cmd, delivered = mailbox.deliver(box, "display", {}, sleep=viewer_ready_after_first_send)
    assert delivered and cmd[kw("id")] == 2


def test_deliver_gives_up_without_a_viewer(tmp_path):
    box = tmp_path / "to-viewer.edn"
    _, delivered = mailbox.deliver(box, "display", {}, timeout_s=9, sleep=lambda _: None)
    assert not delivered
