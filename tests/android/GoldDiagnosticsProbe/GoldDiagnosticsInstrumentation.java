/* SPDX-License-Identifier: Apache-2.0 */
package org.lineageos.gold.diagnosticsprobe;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import org.json.JSONArray;
import org.json.JSONObject;
import java.lang.reflect.Method;
import java.util.List;

/** Exercise the installed Diagnostics UI with owned protobufs, never BatteryService injection. */
public final class GoldDiagnosticsInstrumentation extends Instrumentation {
    private final JSONArray results = new JSONArray();
    private int failed;
    @Override public void onCreate(Bundle args) { super.onCreate(args); start(); }
    private void test(String name, String setter, Object value, int launch, String key,
            boolean visible, boolean unknown, boolean legacy) throws Exception {
        ClassLoader loader = getTargetContext().getClassLoader();
        Class<?> info = loader.loadClass("com.android.devicediagnostics.Protos$BatteryInfo");
        Object builder = info.getMethod("newBuilder").invoke(null);
        if (setter != null) {
            Class<?> type = value instanceof Long ? long.class : int.class;
            builder.getClass().getMethod(setter, type).invoke(builder, value);
        }
        Object message = builder.getClass().getMethod("build").invoke(builder);
        byte[] bytes = (byte[]) message.getClass().getMethod("toByteArray").invoke(message);
        Intent intent = new Intent().setClassName("com.android.devicediagnostics",
                "com.android.devicediagnostics.BatteryActivity")
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                .putExtra("battery_info", bytes).putExtra("vsr_level", launch);
        Activity activity = startActivitySync(intent);
        waitForIdleSync();
        JSONObject result = new JSONObject().put("case", name);
        Throwable[] error = new Throwable[1];
        runOnMainSync(() -> {
            try {
                Object manager = activity.getClass().getMethod("getSupportFragmentManager").invoke(activity);
                List<?> fragments = (List<?>) manager.getClass().getMethod("getFragments").invoke(manager);
                if (fragments.size() != 1) throw new AssertionError("expected one BatteryInfoFragment");
                Object fragment = fragments.get(0);
                Method find = fragment.getClass().getMethod("findPreference", CharSequence.class);
                Object preference = find.invoke(fragment, key);
                boolean actual = (boolean) preference.getClass().getMethod("isVisible").invoke(preference);
                CharSequence summary = (CharSequence) preference.getClass().getMethod("getSummary").invoke(preference);
                int unknownId = activity.getResources().getIdentifier("unknown", "string", "com.android.devicediagnostics");
                boolean unknownMatched = !unknown || activity.getString(unknownId).contentEquals(summary);
                Object legacyPref = find.invoke(fragment, "legacy_health");
                boolean actualLegacy = (boolean) legacyPref.getClass().getMethod("isVisible").invoke(legacyPref);
                boolean passed = actual == visible && unknownMatched && actualLegacy == legacy;
                result.put("visible", actual).put("expected_visible", visible)
                        .put("unknown_matched", unknownMatched).put("legacy_visible", actualLegacy)
                        .put("passed", passed);
                if (!passed) failed++;
            } catch (Throwable e) { error[0] = e; }
            finally { activity.finish(); }
        });
        waitForIdleSync();
        if (error[0] != null) throw new RuntimeException(error[0]);
        results.put(result);
        Bundle update = new Bundle(); update.putString("case", result.toString()); sendStatus(0, update);
    }
    @Override public void onStart() {
        Bundle output = new Bundle();
        try {
            test("health_missing", null, null, 31, "health", false, false, true);
            for (int value : new int[]{Integer.MIN_VALUE,-1,0,1,100,101,Integer.MAX_VALUE}) {
                boolean valid = value >= 1 && value <= 100;
                test("health_" + value, "setStateOfHealth", value, 31, "health", valid, false, !valid);
            }
            long future = System.currentTimeMillis() / 1000 + 86400;
            for (String setter : new String[]{"setManufactureTimestamp","setFirstUsageTimestamp"}) {
                String key = setter.equals("setManufactureTimestamp") ? "manufacture_date" : "first_usage_date";
                for (long value : new long[]{Long.MIN_VALUE,-1,0,1,future,Long.MAX_VALUE}) {
                    test(key + "_" + value, setter, value, 31, key, value == 1, false, true);
                }
            }
            test("cycle_missing_pre34", null, null, 31, "cycle_count", false, true, true);
            test("cycle_missing_35", null, null, 35, "cycle_count", true, true, true);
            for (int value : new int[]{Integer.MIN_VALUE,-1,0,1,Integer.MAX_VALUE}) {
                test("cycle_pre34_" + value, "setCycleCount", value, 31, "cycle_count", value >= 0, value < 0, true);
            }
            test("cycle_negative_35", "setCycleCount", -1, 35, "cycle_count", true, true, true);
            output.putString("result", new JSONObject().put("cases", results)
                    .put("count", results.length()).put("failed", failed)
                    .put("all_passed", failed == 0).toString());
            finish(Activity.RESULT_OK, output);
        } catch (Throwable e) {
            output.putString("error", e.toString());
            output.putString("partial", results.toString());
            finish(Activity.RESULT_CANCELED, output);
        }
    }
}
