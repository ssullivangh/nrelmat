<%inherit file="tmBase.mak"/>


<%block name="blkHead">
<!-- tmLogin.blkHead: overrides tmBase.mak: blkHead -->
<script language="javascript" type="text/javascript">
function setInitialFocus() {
  document.forma.userid.focus();
}
</script>
</%block>


<%block name="blkTitle"> Login </%block>


<!-- tmLogin.body: start -->

<div id="form">

Please use your NREL network ID and password.
<form action="" method="post" name="forma">
  Userid: <input type="text" name="userid" value="${userid}"/><br/>
  Password: <input type="password" name="password" value="${password}"/><br/>
  <input type="submit" name="submitTag" value="Log In"/>
</form>

</div>

<!-- tmLogin.body: end -->
