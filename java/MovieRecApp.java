import javax.swing.*;
import javax.swing.border.EmptyBorder;
import javax.swing.table.*;
import java.awt.*;
import java.awt.event.*;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.List;

/**
 * CineMatch - Java Swing desktop client for the Python recommendation backend.
 * It talks to http://127.0.0.1:5000 (our OWN Flask server, no external API).
 *
 *   javac MovieRecApp.java && java MovieRecApp
 */
public class MovieRecApp {
    static final String BASE = System.getProperty("backend", "http://127.0.0.1:5000");
    static final Color BG = new Color(0x0b0e18), CARD = new Color(0x141a2e), LINE = new Color(0x252d4a), FG = new Color(0xece9e2),
            MUTE = new Color(0x8b93ad), AMB = new Color(0xf5b94a), TEAL = new Color(0x4fd1c5), ROSE = new Color(0xf0647a), VIOLET = new Color(0x8b7cf6);
    static final Font BODY = new Font("SansSerif", Font.PLAIN, 14), BOLD = new Font("SansSerif", Font.BOLD, 14), TITLE = new Font("Serif", Font.BOLD, 26);
    static final HttpClient HTTP = HttpClient.newHttpClient();

    // ------------------------------------------------------------------ tiny JSON parser (no libraries)
    static final class Json {
        final String s; int i = 0;
        Json(String s) { this.s = s; }
        static Object parse(String s) { Json j = new Json(s); return j.val(); }
        void ws() { while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++; }
        Object val() {
            ws(); char c = s.charAt(i);
            if (c == '{') { Map<String, Object> m = new LinkedHashMap<>(); i++; ws(); if (s.charAt(i) == '}') { i++; return m; }
                while (true) { ws(); String k = str(); ws(); i++; m.put(k, val()); ws(); if (s.charAt(i++) == '}') return m; } }
            if (c == '[') { List<Object> l = new ArrayList<>(); i++; ws(); if (s.charAt(i) == ']') { i++; return l; }
                while (true) { l.add(val()); ws(); if (s.charAt(i++) == ']') return l; } }
            if (c == '"') return str();
            if (s.startsWith("true", i)) { i += 4; return true; }
            if (s.startsWith("false", i)) { i += 5; return false; }
            if (s.startsWith("null", i)) { i += 4; return null; }
            int st = i; while (i < s.length() && "+-0123456789.eE".indexOf(s.charAt(i)) >= 0) i++;
            return Double.parseDouble(s.substring(st, i));
        }
        String str() {
            StringBuilder b = new StringBuilder(); i++;
            while (s.charAt(i) != '"') { char c = s.charAt(i++);
                if (c == '\\') { char e = s.charAt(i++);
                    switch (e) { case 'n': b.append('\n'); break; case 't': b.append('\t'); break;
                        case 'u': b.append((char) Integer.parseInt(s.substring(i, i + 4), 16)); i += 4; break; default: b.append(e); } }
                else b.append(c); }
            i++; return b.toString();
        }
    }
    @SuppressWarnings("unchecked") static Map<String, Object> obj(Object o) { return (Map<String, Object>) o; }
    @SuppressWarnings("unchecked") static List<Object> arr(Object o) { return (List<Object>) o; }
    static double num(Object o) { return o == null ? 0 : ((Number) o).doubleValue(); }
    static String enc(String s) { return URLEncoder.encode(s, StandardCharsets.UTF_8); }

    /** GET a JSON document from our backend (throws with the server's error message on 4xx/5xx). */
    static Object fetch(String path) throws Exception {
        HttpResponse<String> r = HTTP.send(HttpRequest.newBuilder(URI.create(BASE + path)).GET().build(), HttpResponse.BodyHandlers.ofString());
        Object j = Json.parse(r.body());
        if (r.statusCode() >= 400) throw new RuntimeException(j instanceof Map && obj(j).get("error") != null ? obj(j).get("error").toString() : "HTTP " + r.statusCode());
        return j;
    }

    // ------------------------------------------------------------------ UI helpers
    static JButton button(String t) {
        JButton b = new JButton(t) { protected void paintComponent(Graphics g) { Graphics2D g2 = (Graphics2D) g.create(); g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            g2.setPaint(new GradientPaint(0, 0, AMB, getWidth(), 0, new Color(0xff8a4c))); g2.fillRoundRect(0, 0, getWidth(), getHeight(), getHeight(), getHeight()); g2.dispose(); super.paintComponent(g); } };
        b.setContentAreaFilled(false); b.setBorderPainted(false); b.setFocusPainted(false); b.setForeground(new Color(0x1b1405)); b.setFont(BOLD);
        b.setBorder(new EmptyBorder(9, 22, 9, 22)); b.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)); return b;
    }
    static JLabel label(String t, Font f, Color c) { JLabel l = new JLabel(t); l.setFont(f); l.setForeground(c); return l; }
    static void style(JComponent c) { c.setBackground(new Color(0x0d1120)); c.setForeground(FG); c.setFont(BODY); c.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(LINE), new EmptyBorder(6, 10, 6, 10))); if (c instanceof JTextField) ((JTextField) c).setCaretColor(AMB); }
    static JPanel panel(LayoutManager l) { JPanel p = new JPanel(l); p.setBackground(BG); return p; }

    /** Deterministic poster gradient from the first genre. */
    static final Map<String, Color[]> GCOL = new HashMap<>();
    static { String[][] d = {{"Action", "ff6a3d", "7a1e1e"}, {"Adventure", "2fb67c", "0f4c5c"}, {"Animation", "ffb347", "d1478c"}, {"Children's", "ffd166", "06a77d"}, {"Comedy", "ffd23f", "ee6c4d"},
        {"Crime", "6b7280", "1f2937"}, {"Documentary", "38bdf8", "14532d"}, {"Drama", "a78bfa", "312e81"}, {"Fantasy", "c084fc", "4c1d95"}, {"Film-Noir", "94a3b8", "0f172a"}, {"Horror", "dc2626", "1c0a0a"},
        {"Musical", "f472b6", "6d28d9"}, {"Mystery", "5eead4", "134e4a"}, {"Romance", "fb7185", "9f1239"}, {"Sci-Fi", "22d3ee", "1e1b4b"}, {"Thriller", "f97316", "18181b"}, {"War", "a3a380", "3f3f2c"}, {"Western", "e0a458", "7c3f00"}};
        for (String[] r : d) GCOL.put(r[0], new Color[]{Color.decode("#" + r[1]), Color.decode("#" + r[2])}); }

    /** One result "card" row renderer: poster chip + title + genres + score bars. */
    static class MovieRenderer extends JPanel implements TableCellRenderer {
        Map<String, Object> m; boolean sel; int col;
        MovieRenderer() { setOpaque(false); }
        public Component getTableCellRendererComponent(JTable t, Object v, boolean s, boolean f, int r, int c) { m = (Map<String, Object>) v; sel = s; col = c; return this; }
        protected void paintComponent(Graphics g0) {
            Graphics2D g = (Graphics2D) g0.create(); g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON); g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            int w = getWidth(), h = getHeight(); g.setColor(sel ? new Color(0x1f2747) : (col % 2 == 0 ? CARD : CARD)); g.fillRect(0, 0, w, h); g.setColor(LINE); g.drawLine(0, h - 1, w, h - 1);
            if (m == null) return;
            List<Object> gl = arr(m.get("genres")); Color[] gc = GCOL.getOrDefault(String.valueOf(gl.get(0)), new Color[]{MUTE, BG});
            if (col == 0) { g.setPaint(new GradientPaint(10, 8, gc[0], 40, h - 8, gc[1])); g.fillRoundRect(10, 8, 44, h - 16, 10, 10);
                g.setColor(new Color(255, 255, 255, 190)); g.setFont(new Font("Serif", Font.BOLD, 24)); String t = m.get("title").toString().replaceFirst("(?i)^(the|a|an) ", ""); g.drawString(t.substring(0, 1).toUpperCase(), 24, h / 2 + 8);
                g.setColor(FG); g.setFont(new Font("Serif", Font.BOLD, 16)); g.drawString(m.get("title").toString(), 66, 26);
                g.setColor(MUTE); g.setFont(new Font("SansSerif", Font.PLAIN, 12)); g.drawString((int) num(m.get("year")) + "  ·  " + String.join(", ", gl.stream().map(Object::toString).toList()), 66, 45);
                if (m.containsKey("shared_keywords") && !arr(m.get("shared_keywords")).isEmpty()) { g.setColor(TEAL); g.drawString("shared: " + arr(m.get("shared_keywords")).stream().map(Object::toString).reduce((a, b) -> a + ", " + b).orElse(""), 66, 62); } }
            else if (col == 1) { g.setFont(BOLD); g.setColor(AMB); g.drawString("★ " + num(m.get("avg_rating")), 12, 26); g.setColor(MUTE); g.setFont(new Font("SansSerif", Font.PLAIN, 12)); g.drawString((int) num(m.get("n_ratings")) + " ratings", 12, 45); }
            else if (col == 2) { if (m.containsKey("match")) { bar(g, 12, 14, w - 70, "Match", num(m.get("match")) / 100, AMB); bar(g, 12, 34, w - 70, "Content", num(m.get("content")), TEAL); bar(g, 12, 54, w - 70, "Collab", num(m.get("collab")), VIOLET); }
                else if (m.containsKey("predicted")) { g.setFont(new Font("Serif", Font.BOLD, 24)); g.setColor(AMB); g.drawString(String.format("%.2f", num(m.get("predicted"))), 12, 38); g.setFont(new Font("SansSerif", Font.PLAIN, 12)); g.setColor(MUTE); g.drawString("predicted ★", 12, 56); } }
            g.dispose();
        }
        void bar(Graphics2D g, int x, int y, int w, String l, double v, Color c) { g.setFont(new Font("SansSerif", Font.PLAIN, 11)); g.setColor(MUTE); g.drawString(l, x, y + 9); g.setColor(new Color(255, 255, 255, 25)); g.fillRoundRect(x + 52, y + 2, w - 52, 7, 7, 7); g.setColor(c); g.fillRoundRect(x + 52, y + 2, (int) Math.max(4, (w - 52) * Math.min(1, v)), 7, 7, 7); g.drawString("", 0, 0); g.setColor(FG); g.drawString((int) Math.round(v * 100) + "%", x + w + 6, y + 9); }
    }

    static JTable movieTable(DefaultTableModel model) {
        JTable t = new JTable(model); t.setRowHeight(72); t.setShowGrid(false); t.setBackground(CARD); t.setIntercellSpacing(new Dimension(0, 0)); t.setTableHeader(null); t.setFillsViewportHeight(true);
        MovieRenderer r = new MovieRenderer(); for (int i = 0; i < 3; i++) t.getColumnModel().getColumn(i).setCellRenderer(r);
        t.getColumnModel().getColumn(0).setPreferredWidth(520); t.getColumnModel().getColumn(1).setPreferredWidth(140); t.getColumnModel().getColumn(2).setPreferredWidth(260); return t;
    }
    static DefaultTableModel rows(List<Object> movies) { DefaultTableModel m = new DefaultTableModel(0, 3) { public boolean isCellEditable(int r, int c) { return false; } };
        for (Object o : movies) m.addRow(new Object[]{o, o, o}); return m; }
    static JScrollPane scroll(JComponent c) { JScrollPane s = new JScrollPane(c); s.setBorder(BorderFactory.createLineBorder(LINE)); s.getViewport().setBackground(CARD); return s; }

    // ------------------------------------------------------------------ tabs
    static JTextField qField = new JTextField(), uField = new JTextField("42", 6), puField = new JTextField("7", 6), pmField = new JTextField(24);
    static JLabel status = label(" ", BODY, MUTE);

    static JPanel recommendTab() {
        JPanel p = panel(new BorderLayout(0, 12)); p.setBorder(new EmptyBorder(16, 20, 16, 20));
        style(qField); qField.setPreferredSize(new Dimension(420, 40)); qField.putClientProperty("JTextField.placeholderText", "Type a movie name, e.g. Inception");
        JComboBox<String> mode = new JComboBox<>(new String[]{"hybrid", "content", "collab"}); JSpinner n = new JSpinner(new SpinnerNumberModel(12, 3, 40, 1));
        JSlider alpha = new JSlider(0, 100, 45); alpha.setBackground(BG); alpha.setPreferredSize(new Dimension(120, 28)); JLabel hint = label("", BODY, MUTE);
        JButton go = button("Recommend");
        JPanel top = panel(new FlowLayout(FlowLayout.LEFT, 10, 0)); top.add(label("Movie", BOLD, AMB)); top.add(qField); top.add(label("Mode", BODY, MUTE)); top.add(mode); top.add(label("Top N", BODY, MUTE)); top.add(n);
        top.add(label("Content weight", BODY, MUTE)); top.add(alpha); top.add(go);
        JTable table = movieTable(rows(new ArrayList<>())); JTextArea trace = new JTextArea(6, 40); trace.setEditable(false); trace.setLineWrap(true); trace.setWrapStyleWord(true); style(trace); trace.setForeground(MUTE);
        JLabel title = label("Search a movie to get recommendations", new Font("Serif", Font.BOLD, 20), FG);
        JPanel mid = panel(new BorderLayout(0, 8)); mid.add(title, BorderLayout.NORTH); mid.add(scroll(table), BorderLayout.CENTER);
        JPanel bot = panel(new BorderLayout(0, 4)); bot.add(label("Behind the scenes (backend trace)", BOLD, TEAL), BorderLayout.NORTH); bot.add(scroll(trace), BorderLayout.CENTER);
        p.add(top, BorderLayout.NORTH); p.add(mid, BorderLayout.CENTER); p.add(bot, BorderLayout.SOUTH);
        Runnable run = () -> { String q = qField.getText().trim(); if (q.isEmpty()) return; status.setText("Asking backend…");
            new SwingWorker<Map<String, Object>, Void>() {
                protected Map<String, Object> doInBackground() throws Exception { return obj(fetch("/api/recommend?title=" + enc(q) + "&mode=" + mode.getSelectedItem() + "&n=" + n.getValue() + "&alpha=" + alpha.getValue() / 100.0)); }
                protected void done() { try { Map<String, Object> d = get(); Map<String, Object> qm = obj(d.get("query")); title.setText("Because you liked " + qm.get("title") + " (" + (int) num(qm.get("year")) + ")");
                        table.setModel(rows(arr(d.get("results")))); MovieRenderer r = new MovieRenderer(); for (int i = 0; i < 3; i++) table.getColumnModel().getColumn(i).setCellRenderer(r);
                        table.getColumnModel().getColumn(0).setPreferredWidth(520); table.getColumnModel().getColumn(1).setPreferredWidth(140); table.getColumnModel().getColumn(2).setPreferredWidth(260);
                        StringBuilder sb = new StringBuilder(); int k = 1; for (Object o : arr(d.get("trace"))) { Map<String, Object> s = obj(o); sb.append(k++).append(". ").append(s.get("step")).append(s.get("ms") != null ? "  [" + s.get("ms") + " ms]" : "").append("\n   ").append(s.get("detail")).append("\n"); }
                        trace.setText(sb.toString()); trace.setCaretPosition(0); status.setText("Done in " + d.get("total_ms") + " ms");
                    } catch (Exception e) { String m = e.getCause() != null ? e.getCause().getMessage() : e.getMessage(); status.setText("Error: " + m); JOptionPane.showMessageDialog(p, m, "Backend", JOptionPane.WARNING_MESSAGE); } } }.execute(); };
        go.addActionListener(e -> run.run()); qField.addActionListener(e -> run.run()); return p;
    }

    static JPanel userTab() {
        JPanel p = panel(new BorderLayout(0, 12)); p.setBorder(new EmptyBorder(16, 20, 16, 20)); style(uField); JButton go = button("Recommend for user"), rnd = button("Random user");
        JPanel top = panel(new FlowLayout(FlowLayout.LEFT, 10, 0)); top.add(label("User ID (1-6040)", BOLD, AMB)); top.add(uField); top.add(go); top.add(rnd);
        JLabel prof = label("Pick a user — matrix factorisation predicts what they'd rate every unseen movie.", BODY, MUTE); JTable table = movieTable(rows(new ArrayList<>()));
        JPanel mid = panel(new BorderLayout(0, 8)); mid.add(prof, BorderLayout.NORTH); mid.add(scroll(table), BorderLayout.CENTER); p.add(top, BorderLayout.NORTH); p.add(mid, BorderLayout.CENTER);
        Runnable run = () -> new SwingWorker<Map<String, Object>, Void>() {
            protected Map<String, Object> doInBackground() throws Exception { return obj(fetch("/api/user/" + Integer.parseInt(uField.getText().trim()) + "/recommend?n=12")); }
            protected void done() { try { Map<String, Object> d = get(), u = obj(d.get("user")); StringBuilder fav = new StringBuilder(); for (Object o : arr(u.get("fav_genres"))) fav.append(arr(o).get(0)).append(" ");
                    prof.setText("<html>User " + (int) num(u.get("user_id")) + " · " + (int) num(u.get("n_ratings")) + " ratings · mean " + u.get("mean_rating") + "★ · favourite genres: " + fav + "</html>"); prof.setForeground(FG);
                    table.setModel(rows(arr(d.get("results")))); MovieRenderer r = new MovieRenderer(); for (int i = 0; i < 3; i++) table.getColumnModel().getColumn(i).setCellRenderer(r);
                    table.getColumnModel().getColumn(0).setPreferredWidth(520); status.setText("Done in " + d.get("total_ms") + " ms");
                } catch (Exception e) { String m = e.getCause() != null ? e.getCause().getMessage() : e.getMessage(); status.setText("Error: " + m); JOptionPane.showMessageDialog(p, m, "Backend", JOptionPane.WARNING_MESSAGE); } } }.execute();
        go.addActionListener(e -> run.run()); rnd.addActionListener(e -> { uField.setText("" + (1 + new Random().nextInt(6040))); run.run(); }); return p;
    }

    static JPanel predictTab() {
        JPanel p = panel(new BorderLayout(0, 12)); p.setBorder(new EmptyBorder(16, 20, 16, 20)); style(puField); style(pmField); JButton go = button("Predict rating");
        JPanel top = panel(new FlowLayout(FlowLayout.LEFT, 10, 0)); top.add(label("User ID", BOLD, AMB)); top.add(puField); top.add(label("Movie", BOLD, AMB)); top.add(pmField); top.add(go);
        JLabel big = label("–", new Font("Serif", Font.BOLD, 72), AMB), sub = label("Enter a user and a movie name", BODY, MUTE); JTextArea parts = new JTextArea(); parts.setEditable(false); style(parts); parts.setFont(new Font("Monospaced", Font.PLAIN, 14));
        JPanel c = panel(new BorderLayout(0, 10)); JPanel h = panel(new GridLayout(0, 1)); h.add(big); h.add(sub); c.add(h, BorderLayout.NORTH); c.add(parts, BorderLayout.CENTER); p.add(top, BorderLayout.NORTH); p.add(c, BorderLayout.CENTER);
        go.addActionListener(e -> new SwingWorker<Map<String, Object>, Void>() {
            protected Map<String, Object> doInBackground() throws Exception { List<Object> s = arr(fetch("/api/search?q=" + enc(pmField.getText()) + "&limit=1")); if (s.isEmpty()) throw new RuntimeException("Movie not found");
                return obj(fetch("/api/predict?user=" + puField.getText().trim() + "&movie=" + (int) num(obj(s.get(0)).get("movie_id")))); }
            protected void done() { try { Map<String, Object> d = get(), P = obj(d.get("parts")), mv = obj(d.get("movie")); big.setText(String.format("%.2f ★", num(d.get("predicted"))));
                    sub.setText("<html>" + mv.get("title") + " (" + (int) num(mv.get("year")) + ") for user " + (int) num(d.get("user_id")) + (d.get("actual") != null ? " — actual rating was " + (int) num(d.get("actual")) + "★" : " — user has not rated it") + "</html>");
                    parts.setText(String.format("  r̂ = μ + b_user + b_movie + p·q%n%n  global mean  μ     = %6.2f%n  user bias   b_u   = %+6.2f%n  movie bias  b_i   = %+6.2f%n  taste match p·q   = %+6.2f", num(P.get("global_mean")), num(P.get("user_bias")), num(P.get("item_bias")), num(P.get("interaction"))));
                } catch (Exception ex) { String m = ex.getCause() != null ? ex.getCause().getMessage() : ex.getMessage(); status.setText("Error: " + m); JOptionPane.showMessageDialog(p, m, "Backend", JOptionPane.WARNING_MESSAGE); } } }.execute()); return p;
    }

    /** Analytics: model table, confusion matrix (painted), rating histogram. */
    static class Analytics extends JPanel {
        Map<String, Object> M, S;
        Analytics() { setBackground(BG); setPreferredSize(new Dimension(1100, 640)); }
        void load() { new SwingWorker<Void, Void>() { protected Void doInBackground() throws Exception { M = obj(fetch("/api/metrics")); S = obj(fetch("/api/stats")); return null; } protected void done() { repaint(); } }.execute(); }
        protected void paintComponent(Graphics g0) {
            super.paintComponent(g0); Graphics2D g = (Graphics2D) g0; g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON); g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            if (M == null) { g.setColor(MUTE); g.setFont(BODY); g.drawString("Loading analytics from backend…", 30, 40); return; }
            g.setFont(TITLE); g.setColor(FG); g.drawString("Model evaluation & dataset", 24, 40); g.setFont(BODY); g.setColor(MUTE);
            g.drawString(String.format("%,d ratings · %,d users · %,d movies · sparsity %.1f%% · test split %,d ratings", (long) num(S.get("n_ratings")), (long) num(S.get("n_users")), (long) num(S.get("n_movies")), 100 * num(S.get("sparsity")), (long) num(obj(M.get("split")).get("test"))), 24, 62);
            // model table
            panelBox(g, 24, 84, 500, 190, "Model comparison (RMSE / MAE)"); int y = 142; g.setFont(BOLD); List<Object> ms = arr(M.get("models")); double best = 9; for (Object o : ms) best = Math.min(best, num(obj(o).get("rmse")));
            for (Object o : ms) { Map<String, Object> r = obj(o); boolean b = num(r.get("rmse")) == best; g.setColor(b ? AMB : FG); g.setFont(b ? BOLD : BODY); g.drawString(r.get("model").toString(), 44, y); g.drawString(String.format("%.4f", num(r.get("rmse"))), 330, y); g.drawString(String.format("%.4f", num(r.get("mae"))), 430, y); y += 30; }
            // metrics
            Map<String, Object> c = obj(M.get("confusion_binary")); panelBox(g, 548, 84, 528, 190, "Test metrics  (liked = rating ≥ 4)"); String[] ln = {"Accuracy", "Precision", "Recall", "F1-score", "ROC-AUC"}; String[] kk = {"accuracy", "precision", "recall", "f1", "auc"};
            for (int i = 0; i < 5; i++) { int x = 568 + i * 100; g.setFont(new Font("Serif", Font.BOLD, 26)); g.setColor(TEAL); g.drawString(String.format("%.1f%%", 100 * num(c.get(kk[i]))), x, 160); g.setFont(new Font("SansSerif", Font.PLAIN, 12)); g.setColor(MUTE); g.drawString(ln[i], x, 180); }
            // confusion matrix
            panelBox(g, 24, 296, 500, 320, "Confusion matrix (like / dislike)"); List<Object> mat = arr(c.get("matrix")); double mx = 0; for (Object r : mat) for (Object v : arr(r)) mx = Math.max(mx, num(v)); String[] names = {"TN", "FP", "FN", "TP"};
            for (int i = 0; i < 2; i++) for (int j = 0; j < 2; j++) { double v = num(arr(arr(mat).get(i)).get(j)); Color base = i == j ? new Color(0x2f9e83) : new Color(0xb4455a); int x = 150 + j * 170, yy = 360 + i * 110;
                g.setColor(new Color(base.getRed(), base.getGreen(), base.getBlue(), (int) (70 + 185 * v / mx))); g.fillRoundRect(x, yy, 160, 100, 14, 14); g.setColor(Color.WHITE); g.setFont(new Font("SansSerif", Font.BOLD, 22)); g.drawString(String.format("%,d", (long) v), x + 30, yy + 52); g.setFont(new Font("SansSerif", Font.PLAIN, 12)); g.drawString(names[i * 2 + j], x + 70, yy + 74); }
            g.setColor(MUTE); g.setFont(BODY); g.drawString("Pred. Dislike", 185, 350); g.drawString("Pred. Like", 365, 350); g.drawString("Actual", 60, 420); g.drawString("Dislike", 60, 440); g.drawString("Actual", 60, 530); g.drawString("Like", 60, 550);
            // rating distribution
            panelBox(g, 548, 296, 528, 320, "Rating distribution"); Map<String, Object> rd = obj(S.get("rating_dist")); double rmx = 0; for (Object v : rd.values()) rmx = Math.max(rmx, num(v));
            int i = 0; for (Map.Entry<String, Object> e : rd.entrySet()) { double v = num(e.getValue()); int h = (int) (200 * v / rmx), x = 590 + i * 90; g.setPaint(new GradientPaint(0, 560 - h, AMB, 0, 560, new Color(0xff8a4c))); g.fillRoundRect(x, 560 - h, 56, h, 8, 8);
                g.setColor(FG); g.setFont(BOLD); g.drawString((int) (v / 1000) + "k", x + 12, 553 - h); g.setColor(MUTE); g.setFont(BODY); g.drawString(e.getKey() + " ★", x + 14, 585); i++; }
        }
        void panelBox(Graphics2D g, int x, int y, int w, int h, String t) { g.setColor(CARD); g.fillRoundRect(x, y, w, h, 16, 16); g.setColor(LINE); g.drawRoundRect(x, y, w, h, 16, 16); g.setColor(AMB); g.setFont(new Font("Serif", Font.BOLD, 16)); g.drawString(t, x + 20, y + 28); }
    }

    // ------------------------------------------------------------------ main
    static JComponent build() {
        UIManager.put("TabbedPane.contentAreaColor", BG); UIManager.put("ScrollBar.thumb", LINE);
        JTabbedPane tabs = new JTabbedPane(); tabs.setBackground(BG); tabs.setForeground(FG); tabs.setFont(BOLD);
        Analytics an = new Analytics(); tabs.addTab("  Discover  ", recommendTab()); tabs.addTab("  For User  ", userTab()); tabs.addTab("  Rating Predictor  ", predictTab()); tabs.addTab("  Analytics  ", an);
        tabs.addChangeListener(e -> { if (tabs.getSelectedComponent() == an && an.M == null) an.load(); });
        JPanel head = panel(new BorderLayout()); head.setBorder(new EmptyBorder(14, 20, 4, 20)); head.add(label("Cine", new Font("Serif", Font.BOLD, 28), FG), BorderLayout.WEST);
        JPanel root = panel(new BorderLayout()); JPanel hb = panel(new FlowLayout(FlowLayout.LEFT, 0, 0)); hb.setBorder(new EmptyBorder(14, 20, 4, 20)); hb.add(label("Cine", new Font("Serif", Font.BOLD, 28), FG)); hb.add(label("Match", new Font("Serif", Font.BOLD, 28), AMB));
        hb.add(label("    Java client · talks to the local Python backend", BODY, MUTE)); root.add(hb, BorderLayout.NORTH); root.add(tabs, BorderLayout.CENTER);
        status.setBorder(new EmptyBorder(4, 20, 8, 20)); root.add(status, BorderLayout.SOUTH); return root;
    }

    public static void main(String[] a) throws Exception {
        if (a.length > 0 && a[0].equals("--selftest")) { selfTest(); return; }
        SwingUtilities.invokeLater(() -> { JFrame f = new JFrame("CineMatch - Movie Recommendation System (Java)"); f.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE); f.setContentPane(build()); f.setSize(1160, 800); f.setLocationRelativeTo(null); f.setVisible(true); });
    }

    /** Headless test: talks to the backend and renders the panel to PNG files. */
    static void selfTest() throws Exception {
        Object r = fetch("/api/recommend?title=" + enc("Inception") + "&n=5"); Map<String, Object> d = obj(r);
        System.out.println("recommend OK -> top: " + obj(arr(d.get("results")).get(0)).get("title"));
        System.out.println("predict OK -> " + obj(fetch("/api/predict?user=7&movie=2")).get("predicted"));
        System.setProperty("java.awt.headless", "true");
        JComponent root = (JComponent) build(); root.setSize(1160, 800); qField.setText("Inception");
        Analytics an = new Analytics(); an.setSize(1100, 640); an.M = obj(fetch("/api/metrics")); an.S = obj(fetch("/api/stats"));
        JTable t = movieTable(rows(arr(d.get("results")))); t.setSize(1000, 5 * 72);
        for (Object[] x : new Object[][]{{an, "java_analytics.png"}, {t, "java_results.png"}}) { JComponent c = (JComponent) x[0]; c.doLayout(); java.awt.image.BufferedImage im = new java.awt.image.BufferedImage(c.getWidth(), c.getHeight(), 1);
            Graphics2D g = im.createGraphics(); c.paint(g); g.dispose(); javax.imageio.ImageIO.write(im, "png", new java.io.File(System.getProperty("out", ".") + "/" + x[1])); }
        System.out.println("rendered PNGs OK");
    }
}
