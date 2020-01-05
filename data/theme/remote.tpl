<html>
  <head>
      <title>Form Example</title>
      <link href="remote.css" rel="stylesheet" />
  </head>
  <body>
    <ul>
    % for service in services:
        <li>{{service}}</li>
    % end
    </ul>

    <form method="post" action="/">
        <input type='submit' name='action' value='{{action}}'>
    </form>
    {{infos if defined('infos') else ''}}

  </body>
</html>
<script>
    if ( window.history.replaceState ) {
        window.history.replaceState( null, null, window.location.href );
    }
</script>