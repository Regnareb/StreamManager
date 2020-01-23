<html>
  <head>
      <title>Form Example</title>
      <link href="remote.css" rel="stylesheet" />
  </head>
  <body class="{{!"started" if action == "STOP" else "stopped"}}">
  <!--<input class="refresh" type="button" value="🔃" onclick="history.go(0)" /> -->
    <ul>
    % for service, stream in services.items():
    % if stream['enabled']:
        <li class="{{!"online" if stream['infos']['online'] == True else "offline"}}"><span class='service_name'>{{service}}</span><span class='category'>{{stream['infos']['category']}}</span><br/><span class='title'>{{stream['infos']['title']}}</span></li>
    % end
    % end
    </ul>

    <form method="post" class="perspective" action="/">
        <button class="action btn btn-8 btn-8f" type='submit' name='action' value='{{action}}'>{{action}}</button>
    </form>

    {{infos if defined('infos') else ''}}

  </body>
</html>
<script>
    if (window.history.replaceState) {
        window.history.replaceState(null, null, window.location.href);
    }
</script>