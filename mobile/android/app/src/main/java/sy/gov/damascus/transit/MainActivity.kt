package sy.gov.damascus.transit

import android.os.Bundle
import com.getcapacitor.BridgeActivity
import com.getcapacitor.Plugin
import java.util.ArrayList

class MainActivity : BridgeActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // All plugins are auto-registered by Capacitor 6 via annotation scanning.
        // Manual registration is only needed for plugins that don't use @CapacitorPlugin.
    }
}
