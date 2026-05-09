package com.bonnie.vta.demo

import android.app.AlertDialog
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.drawerlayout.widget.DrawerLayout
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView

class MainActivity : AppCompatActivity() {

    private lateinit var statusText: TextView
    private lateinit var inputField: EditText
    private lateinit var sendButton: Button
    private lateinit var recyclerView: RecyclerView
    private val messages = mutableListOf<ChatMessage>()
    private lateinit var chatAdapter: ChatAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        for (i in 0 until 10) {
            val sender = if (i % 2 == 0) "User" else "Bot"
            val text = when {
                i == 0 -> "Hello! How can I help you today?"
                i == 1 -> "Hi Bot, I need help with my order #12345"
                i == 2 -> "Sure! Let me look that up for you. Can you confirm your email?"
                i == 3 -> "myemail@example.com"
                i == 4 -> "Thanks. Your order #12345 is currently being processed."
                i == 5 -> "When will it be delivered?"
                i == 6 -> "Estimated delivery is May 10th. Would you like to track it?"
                i == 7 -> "Yes please!"
                i == 8 -> "Here's your tracking link. Anything else?"
                else -> "No that's all, thanks!"
            }
            messages.add(ChatMessage(sender, text, i))
        }

        chatAdapter = ChatAdapter(messages) { msg ->
            statusText.text = "Clicked: ${msg.sender}: ${msg.text.take(40)}..."
        }

        setContentView(buildUI())

        if (savedInstanceState == null) {
            supportFragmentManager.beginTransaction()
                .add(R.id.fragment_container, StatusFragment())
                .commitNow()
        }
    }

    override fun onResume() {
        super.onResume()
        statusText.text = "Active | ${this.javaClass.simpleName} | ${messages.size} messages"
    }

    private fun buildUI(): DrawerLayout {
        val drawerLayout = DrawerLayout(this).apply {
            id = View.generateViewId()
        }

        // ── Main content ──────────────────────────────────────────────
        val mainContent = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        }

        // Status bar
        statusText = TextView(this).apply {
            id = R.id.status_text
            textSize = 13f
            setPadding(48, 24, 48, 12)
            setBackgroundColor(0xFFE8E8E8.toInt())
        }
        mainContent.addView(statusText)

        // Fragment container for testing fragment detection
        val fragContainer = FrameLayout(this).apply {
            id = R.id.fragment_container
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 60
            )
        }
        mainContent.addView(fragContainer)

        // Chat RecyclerView
        recyclerView = RecyclerView(this).apply {
            id = R.id.chat_list
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f
            )
            layoutManager = LinearLayoutManager(this@MainActivity)
            adapter = chatAdapter
        }
        mainContent.addView(recyclerView)

        // Input area
        val inputArea = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(16, 8, 16, 8)
            gravity = Gravity.CENTER_VERTICAL
        }

        inputField = EditText(this).apply {
            id = R.id.input_field
            hint = "Type a message..."
            layoutParams = LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
                override fun afterTextChanged(s: Editable?) {
                    sendButton.isEnabled = !s.isNullOrBlank()
                }
            })
        }
        inputArea.addView(inputField)

        sendButton = Button(this).apply {
            id = R.id.btn_send
            text = "Send"
            isEnabled = false
            setOnClickListener {
                val text = inputField.text?.toString() ?: return@setOnClickListener
                messages.add(ChatMessage("User", text, messages.size))
                chatAdapter.notifyItemInserted(messages.size - 1)
                recyclerView.scrollToPosition(messages.size - 1)
                inputField.setText("")
                statusText.text = "Sent at ${System.currentTimeMillis() % 100000}"
            }
        }
        inputArea.addView(sendButton)
        mainContent.addView(inputArea)

        // Dialog trigger button
        mainContent.addView(Button(this).apply {
            id = R.id.btn_show_dialog
            text = "Show Dialog"
            setOnClickListener {
                val dialog = AlertDialog.Builder(this@MainActivity)
                    .setTitle("Confirm Action")
                    .setMessage("Are you sure you want to proceed?")
                    .setPositiveButton("Confirm") { _, _ ->
                        statusText.text = "Dialog: Confirmed"
                    }
                    .setNegativeButton("Cancel") { _, _ ->
                        statusText.text = "Dialog: Cancelled"
                    }
                    .create()
                com.bonnie.vta.VtaSdk.trackDialog(dialog)
                dialog.show()
            }
        })

        // Hidden view (should NOT appear in vta state)
        mainContent.addView(TextView(this).apply {
            id = R.id.hidden_view
            text = "This text should never appear in vta state output"
            visibility = View.GONE
        })

        // Drawer toggle button
        mainContent.addView(Button(this).apply {
            id = R.id.btn_toggle_drawer
            text = "Open Menu"
            setOnClickListener {
                if (drawerLayout.isDrawerOpen(Gravity.END)) {
                    drawerLayout.closeDrawer(Gravity.END)
                } else {
                    drawerLayout.openDrawer(Gravity.END)
                }
            }
        })

        drawerLayout.addView(mainContent)

        // ── Right drawer ──────────────────────────────────────────────
        val drawerContent = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 80, 48, 48)
            setBackgroundColor(0xFFFFFFFF.toInt())
            layoutParams = DrawerLayout.LayoutParams(
                600, ViewGroup.LayoutParams.MATCH_PARENT, Gravity.END
            )
        }

        drawerContent.addView(TextView(this).apply {
            text = "Menu"
            textSize = 20f
            setPadding(0, 0, 0, 40)
        })

        val drawerItems = listOf(
            R.id.drawer_settings to "Settings",
            R.id.drawer_profile to "Profile",
            R.id.drawer_help to "Help"
        )
        for ((id, label) in drawerItems) {
            drawerContent.addView(Button(this).apply {
                this.id = id
                text = label
                setOnClickListener {
                    statusText.text = "Drawer: $label clicked"
                    drawerLayout.closeDrawer(Gravity.END)
                }
            })
        }

        drawerLayout.addView(drawerContent)

        return drawerLayout
    }
}

data class ChatMessage(
    val sender: String,
    val text: String,
    val index: Int
)

class ChatAdapter(
    private val messages: List<ChatMessage>,
    private val onItemClick: (ChatMessage) -> Unit
) : RecyclerView.Adapter<ChatAdapter.VH>() {

    class VH(val root: ViewGroup, val title: TextView, val message: TextView) : RecyclerView.ViewHolder(root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val container = LinearLayout(parent.context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 16, 32, 16)
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        }
        val title = TextView(parent.context).apply {
            id = R.id.item_title
            textSize = 12f
            setTextColor(0xFF666666.toInt())
        }
        container.addView(title)
        val message = TextView(parent.context).apply {
            id = R.id.item_message
            textSize = 16f
            setTextColor(0xFF1A1A1A.toInt())
            isClickable = true
            isFocusable = true
        }
        container.addView(message)
        return VH(container, title, message)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val msg = messages[position]
        holder.title.text = msg.sender
        holder.message.text = msg.text
        // Make the whole item clickable, and the message text individually clickable too
        holder.root.setOnClickListener { onItemClick(msg) }
        holder.root.isClickable = true
        holder.message.setOnClickListener { onItemClick(msg) }
    }

    override fun getItemCount(): Int = messages.size
}

class StatusFragment : Fragment() {
    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View = TextView(requireContext()).apply {
        text = "VTA SDK Active | ${javaClass.simpleName}"
        textSize = 11f
        setPadding(48, 4, 48, 4)
        setBackgroundColor(0xFFE8F5E9.toInt())
        setTextColor(0xFF2E7D32.toInt())
    }
}
