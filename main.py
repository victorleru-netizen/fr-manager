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

# Sauvegarder les avis
def save_avis(avis):
    with open(AVIS_FILE, "w", encoding="utf-8") as f:
        json.dump(avis, f, indent=4, ensure_ascii=False)

# Charger la configuration des rôles staff (Sécurisé)
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Erreur de lecture dans {CONFIG_FILE}, réinitialisation...")
            return {"roles_staff": []}
    return {"roles_staff": []}

# Sauvegarder la configuration
def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

avis_data = load_avis()
config = load_config()

# Fonction pour vérifier si le membre VISÉ est un staff
def est_staff(member: discord.Member) -> bool:
    return any(role.id in config["roles_staff"] for role in member.roles)

@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

# Commande pour configurer les rôles staff
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
    button.callback = lambda i: config_roles_callback(i, embed)
    view.add_item(button)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def config_roles_callback(interaction: discord.Interaction, embed: discord.Embed):
    roles = interaction.guild.roles
    options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in roles if role.name != "@everyone"]

    # Limiter à 25 rôles max affichés (limite Discord pour les SelectOption)
    options = options[:25]

    select = discord.ui.Select(
        placeholder="Sélectionnez les rôles staff...",
        min_values=1,
        max_values=len(options),
        options=options
    )

    async def select_callback(select_interaction: discord.Interaction):
        selected_roles = select_interaction.data["values"]
        config["roles_staff"] = [int(role_id) for role_id in selected_roles]
        save_config(config)

        roles_names = [interaction.guild.get_role(int(role_id)).name for role_id in selected_roles]
        embed.description = f"✅ Rôles éligibles aux avis configurés : {', '.join(roles_names)}"
        await select_interaction.response.edit_message(embed=embed, view=None)

    select.callback = select_callback

    view = discord.ui.View(timeout=None)
    view.add_item(select)

    await interaction.response.edit_message(embed=embed, view=view)


# Système d'autocomplétion pour proposer UNIQUEMENT les membres qui ont le rôle configuré
async def staff_autocomplete(interaction: discord.Interaction, current: str):
    guild = interaction.guild
    if not guild:
        return []
    
    choix = []
    for member in guild.members:
        # Vérifie si le membre a l'un des rôles configurés
        if any(role.id in config["roles_staff"] for role in member.roles):
            if current.lower() in member.name.lower() or current.lower() in (member.nick or "").lower():
                choix.append(app_commands.Choice(name=member.display_name, value=str(member.id)))
    
    # Discord limite l'autocomplétion à 25 résultats maximum
    return choix[:25]


# Commande pour laisser un avis (Accessible par tout le monde)
@bot.tree.command(name="avis", description="Laisser un avis sur un membre du staff")
@app_commands.autocomplete(staff=staff_autocomplete)
@app_commands.describe(staff="Le membre du staff", note="Note de 1 à 5", commentaire="Votre commentaire")
async def avis(interaction: discord.Interaction, staff: str, note: int, commentaire: str):
    # Récupérer l'objet membre à partir de l'ID fourni par l'autocomplétion
    try:
        member = interaction.guild.get_member(int(staff))
        if not member:
            member = await interaction.guild.fetch_member(int(staff))
    except Exception:
        await interaction.response.send_message("❌ Membre introuvable. Veuillez utiliser la liste suggérée.", ephemeral=True)
        return

    # Sécurité : On revérifie si le membre ciblé est bien staff
    if not est_staff(member):
        await interaction.response.send_message(f"❌ **{member.display_name}** ne fait pas partie du staff configuré.", ephemeral=True)
        return

    if note < 1 or note > 5:
        await interaction.response.send_message("❌ La note doit être entre 1 et 5.", ephemeral=True)
        return

    staff_id = str(member.id)
    if staff_id not in avis_data:
        avis_data[staff_id] = {"nom": member.name, "avis": []}

    avis_data[staff_id]["avis"].append({
        "auteur": interaction.user.name,
        "note": note,
        "commentaire": commentaire,
        "date": interaction.created_at.strftime("%d/%m/%Y à %H:%M")
    })
    save_avis(avis_data)

    embed = discord.Embed(
        title="✅ Avis enregistré",
        description=f"Avis de **{interaction.user.name}** pour **{member.mention}** : {note}/5\n**Commentaire** : {commentaire}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


# Commande pour voir les avis
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
        embed = discord.Embed(
            title="❌ Aucun avis trouvé",
            description=f"Aucun avis n'a été enregistré pour **{member.display_name}**.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    avis_list = avis_data[staff_id]["avis"]
    moyenne = sum(a["note"] for a in avis_list) / len(avis_list)

    embed = discord.Embed(
        title=f"📋 Avis pour {member.display_name}",
        color=discord.Color.blue()
    )

    for avis_item in avis_list:
        embed.add_field(
            name=f"⭐ {avis_item['note']}/5 - {avis_item['auteur']}",
            value=f"\"{avis_item['commentaire']}\" - {avis_item['date']}",
            inline=False
        )

    embed.add_field(name="📊 Moyenne", value=f"{moyenne:.2f}/5", inline=False)
    await interaction.response.send_message(embed=embed)

# Récupérer le token depuis les variables d'environnement
TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
