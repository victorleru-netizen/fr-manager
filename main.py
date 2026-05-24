import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from flask import Flask
import threading
from discord import app_commands

# Charger les variables d'environnement
load_dotenv()

# Configuration des intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Initialisation de Flask pour maintenir le bot actif
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# Fichier pour stocker les avis et la configuration
AVIS_FILE = "avis.json"
CONFIG_FILE = "config.json"

# Charger les avis existants (Sécurisé)
def load_avis():
    if os.path.exists(AVIS_FILE):
        try:
            with open(AVIS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Erreur de lecture dans {AVIS_FILE}, réinitialisation...")
            return {}
    return {}

def save_avis(avis):
    with open(AVIS_FILE, "w", encoding="utf-8") as f:
        json.dump(avis, f, indent=4, ensure_ascii=False)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Erreur de lecture dans {CONFIG_FILE}, réinitialisation...")
            return {"roles_staff": []}
    return {"roles_staff": []}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

avis_data = load_avis()
config = load_config()

def est_staff(member: discord.Member) -> bool:
    return any(role.id in config["roles_staff"] for role in member.roles)


# ─── ÉTAPE 2 : FORCE SYNC SUR LE SERVEUR ───
@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        # 1. On efface d'abord les anciennes commandes globales en cache chez Discord
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync(guild=None)
        print("🗑️ Cache des anciennes commandes globales vidé avec succès.")

        # 2. On synchronise instantanément les nouvelles commandes sur TOUS les serveurs actuels du bot
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"⚡ Synchronisation instantanée réussie sur le serveur : {guild.name} ({len(synced)} commandes)")
            
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation : {e}")


# ─── SYSTÈME DE FORMULAIRE (MODAL) ───

class AvisModal(discord.ui.Modal, title="Formulaire d'avis Staff"):
    staff_input = discord.ui.TextInput(
        label="Nom ou Pseudo du Staff",
        placeholder="Ex: Jean / @Jean (sans le @)",
        required=True,
        max_length=50
    )
    note_input = discord.ui.TextInput(
        label="Note (Chiffre de 1 à 5)",
        placeholder="Ex: 5",
        required=True,
        min_length=1,
        max_length=1
    )
    commentaire_input = discord.ui.TextInput(
        label="Votre Commentaire",
        style=discord.TextStyle.long,
        placeholder="Expliquez votre expérience avec ce staff...",
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            note = int(self.note_input.value)
            if note < 1 or note > 5:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ La note doit être un chiffre entier compris entre 1 et 5.", ephemeral=True)
            return

        nom_recherche = self.staff_input.value.lower()
        member = None
        for m in interaction.guild.members:
            if nom_recherche in m.name.lower() or nom_recherche in (m.nick or "").lower():
                if est_staff(m):
                    member = m
                    break
        
        if not member:
            await interaction.response.send_message("❌ Staff introuvable ou le membre trouvé ne possède pas le rôle staff configuré.", ephemeral=True)
            return

        staff_id = str(member.id)
        if staff_id not in avis_data:
            avis_data[staff_id] = {"nom": member.name, "avis": []}

        avis_data[staff_id]["avis"].append({
            "auteur": interaction.user.name,
            "note": note,
            "commentaire": self.commentaire_input.value,
            "date": interaction.created_at.strftime("%d/%m/%Y à %H:%M")
        })
        save_avis(avis_data)

        avis_list = avis_data[staff_id]["avis"]
        moyenne = sum(a["note"] for a in avis_list) / len(avis_list)

        etoiles = "⭐" * note
        embed = discord.Embed(
            title="✅ Avis enregistré",
            color=discord.Color.green()
        )
        embed.description = (
            f"**Staff :** {member.mention}\n"
            f"**Note :** {etoiles}\n"
            f"**Moyenne actuelle :** {moyenne:.1f} / 5\n"
            f"**Commentaire :** *{self.commentaire_input.value}*"
        )
        
        await interaction.response.send_message(embed=embed)


class PersistentAvisView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="FAIRE UN AVIS", style=discord.ButtonStyle.success, custom_id="btn_faire_avis", emoji="✍️")
    async def faire_avis_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AvisModal())


# ─── COMMANDES DU BOT ───

@bot.tree.command(name="avis-view", description="Afficher le bouton permanent pour laisser un avis")
async def avis_view(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent utiliser cette commande.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 Système d'Avis Staff",
        description=(
            "Vous avez interagi avec un membre de notre équipe ? Donnez-nous votre avis !\n\n"
            "Cliquez sur le bouton ci-dessous pour ouvrir le formulaire et évaluer le staff."
        ),
        color=discord.Color.blue()
    )
    
    await interaction.channel.send(embed=embed, view=PersistentAvisView())
    await interaction.response.send_message("✅ Le système d'avis a bien été installé dans ce salon !", ephemeral=True)


@bot.tree.command(name="avis-config", description="Configurer les rôles autorisés à recevoir des avis")
async def avis_config(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Seuls les administrateurs peuvent configurer le bot.", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚙️ Configuration des rôles staff",
        description="Cliquez sur le bouton ci-dessous pour ajouter ou retirer des rôles éligibles aux avis.",
        color=discord.Color.blue()
    )

    view = discord.ui.View(timeout=None)
    button = discord.ui.Button(label="Configurer les rôles", style=discord.ButtonStyle.primary, custom_id="config_roles")
    
    async def config_roles_callback(i: discord.Interaction):
        roles = i.guild.roles
        options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in roles if role.name != "@everyone"][:25]
        
        select = discord.ui.Select(placeholder="Sélectionnez les rôles staff...", min_values=1, max_values=len(options), options=options)
        
        async def select_callback(si: discord.Interaction):
            selected_roles = si.data["values"]
            config["roles_staff"] = [int(role_id) for role_id in selected_roles]
            save_config(config)
            roles_names = [i.guild.get_role(int(role_id)).name for role_id in selected_roles]
            embed.description = f"✅ Rôles éligibles aux avis configurés : {', '.join(roles_names)}"
            await si.response.edit_message(embed=embed, view=None)
            
        select.callback = select_callback
        v = discord.ui.View(timeout=None)
        v.add_item(select)
        await i.response.edit_message(embed=embed, v=v)

    button.callback = config_roles_callback
    view.add_item(button)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def staff_autocomplete(interaction: discord.Interaction, current: str):
    guild = interaction.guild
    if not guild:
        return []
    choix = []
    for member in guild.members:
        if any(role.id in config["roles_staff"] for role in member.roles):
            if current.lower() in member.name.lower() or current.lower() in (member.nick or "").lower():
                choix.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
    return choix[:25]


@bot.tree.command(name="voir_avis", description="Voir les avis d'un membre du staff")
@app_commands.autocomplete(staff=staff_autocomplete)
async def voir_avis(interaction: discord.Interaction, staff: str):
    try:
        member = interaction.guild.get_member(int(staff))
        if not member:
            member = await interaction.guild.fetch_member(int(staff))
    except Exception:
        await interaction.response.send_message("❌ Membre introuvable. Veuillez utiliser la liste suggérée.", ephemeral=True)
        return

    staff_id = str(member.id)
    if staff_id not in avis_data or not avis_data[staff_id]["avis"]:
        embed = discord.Embed(title="❌ Aucun avis trouvé", description=f"Aucun avis n'a été enregistré pour **{member.display_name}**.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    avis_list = avis_data[staff_id]["avis"]
    moyenne = sum(a["note"] for a in avis_list) / len(avis_list)

    embed = discord.Embed(title=f"📋 Profil de {member.display_name}", color=discord.Color.blue())
    embed.description = f"**Staff :** {member.mention}\n**Moyenne globale :** {moyenne:.1f} / 5\n\n─── **Derniers avis reçus** ───"

    for avis_item in avis_list:
        etoiles = "⭐" * avis_item['note']
        embed.add_field(
            name=f"Par {avis_item['auteur']} (le {avis_item['date']})",
            value=f"**Note :** {etoiles}\n**Commentaire :** *{avis_item['commentaire']}*",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
